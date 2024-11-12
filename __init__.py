import datetime
import logging
import smtplib

from azure.identity import ManagedIdentityCredential
from azure.mgmt.compute import ComputeManagementClient

import azure.functions as func

credential = ManagedIdentityCredential()
subscription_id = " "
compute_client = ComputeManagementClient(credential, subscription_id)

def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('\n\n\n\n\n\nPython timer trigger function ran at %s\n\n\n\n\n\n\n', utc_timestamp)

    identify_stale_snapshots()

def identify_stale_snapshots():
    snapshots = compute_client.snapshots.list()
    for snapshot in snapshots:
        logging.info(f"\n\n\n\n\nSnapshot Name: {snapshot.name}, Snapshot ID: {snapshot.id}\n\n\n\n\n\n")
        tags = snapshot.tags
        retention_period = int(tags['RetentionPeriod'])
        created_by = tags['CreatedBy']
        auto_delete = bool(tags['AutoDelete'])
        creation_date = snapshot.time_created
        current_date = datetime.datetime.now(datetime.timezone.utc)
        resource_group_name = snapshot.id.split("/")[4]
        age_minutes = int((current_date - creation_date).total_seconds() / 60)
        logging.info(f"\n\n\n\n\n\n\n\nProcessing snapshot: {snapshot.name},\n\n RG: {resource_group_name},\n\nAutoDelete: {auto_delete},\n\n "
                             f"RetentionPeriod: {retention_period},\n\n CreatedBy: {created_by},\n\n "
                             f"CreationDate: {creation_date}\n\n\n\n\n\n\n")
        if age_minutes > retention_period:
            logging.info("\n\n\n\n\nDeleting Snapshot.... \n\n\n\n\n\n")
            compute_client.snapshots.begin_delete(resource_group_name,snapshot_name=snapshot.name,)
            logging.info(f"\n\n\n\n\nSnapshot has been DELETED {snapshot.name}, Snapshot ID: {snapshot.id}\n\n\n\n\n\n")
            send_deletion_email(created_by, snapshot.name, creation_date, retention_period, age_minutes)
        else:
            notify_owner(created_by, snapshot.name, age_minutes)
            logging.info("\nMAIL SENT AS NOTIFY !!\n\n\n\n\n\n")


    
def send_mail(created_by, email_body):

    sender_email = ' '
    sender_password = ' '       # On your gmail account, enable 2 factor authentication and create an app password, copy and paste it here.

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, created_by, email_body)
    server.quit()

    logging.info('\n\n\n\n\n\n\n\n\n\n\n MAIL HAS BEEN SENT !! !! !!\n\n\n\n\n\n\n\n\n\n\n')

def send_deletion_email(created_by, snapshot_name, creation_date, retention_period, age_minutes):

    email_body = f"""
    Hello,

    The snapshot '{snapshot_name}', created on {creation_date.strftime('%Y-%m-%d')}, 
    has been automatically deleted after reaching its retention period of {retention_period} days.

    Snapshot Details:
    - Name: {snapshot_name}
    - Creation Date: {creation_date.strftime('%Y-%m-%d')}
    - Creation Time: {creation_date.strftime('%H:%M:%S')}
    - Retention Period: {retention_period} minutes
    - Snapshot Age: {age_minutes} minutes

    If you need to retrieve this snapshot, please contact us within 30 days from today.

    Best regards,
    Azure Team
    """
    send_mail(created_by, email_body)



def notify_owner(created_by, snapshot_name, age_minutes):
    email_body = f"""
        Hello,

        The snapshot '{snapshot_name}' is now {age_minutes} minutes old. Please review it to ensure it is still needed. 
        You can either delete the snapshot or update its tag values if necessary.

        Snapshot Details:
        - Name: {snapshot_name}
        - Age: {age_minutes} minutes

        Best regards,
        Azure Team
        """
    send_mail(created_by, email_body)
