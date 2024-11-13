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
    disks = compute_client.disks.list()
    existing_disk_ids = {disk.id for disk in disks}
    unattached_disk_ids = []
    vm_list = compute_client.virtual_machines.list_all()
    attached_disk_ids = set()
    for vm in vm_list:
        if vm.storage_profile.os_disk.managed_disk:
            attached_disk_ids.add(vm.storage_profile.os_disk.managed_disk.id)
    for data_disk in vm.storage_profile.data_disks:
        if data_disk.managed_disk:
            attached_disk_ids.add(data_disk.managed_disk.id)
    for disk in disks:
        if disk.id not in attached_disk_ids:
            unattached_disk_ids.append(disk.id)

    for snapshot in snapshots:
        tags = snapshot.tags
        retention_period = int(tags['RetentionPeriod'])
        created_by = tags['CreatedByEmail']
        creation_date = snapshot.time_created
        current_date = datetime.datetime.now(datetime.timezone.utc)
        resource_group_name = snapshot.id.split("/")[4]
        age_minutes = int((current_date - creation_date).total_seconds() / 60)
        x = False
        y = False

        snapshot_disk_id = snapshot.creation_data.source_resource_id
        if snapshot_disk_id not in existing_disk_ids:
            logging.info(f"Snapshot {snapshot.name} corresponds to a deleted disk.")
            x = True
        if snapshot_disk_id in unattached_disk_ids:
            logging.info(f"Snapshot {snapshot.name} corresponds to a deleted disk.")
            y = True
        inactive = x or y
        
        if age_minutes > retention_period:
            if inactive:
                delete_snapshots(resource_group_name,snapshot.name,created_by,creation_date,retention_period,age_minutes)
                
            else:
                tags['RetentionPeriod'] = str(retention_period + 10)

        if age_minutes > 30:
            pass
            notify(created_by, snapshot.name, creation_date, retention_period, age_minutes)

def delete_snapshots(resource_group_name,snapshotName,created_by,creation_date,retention_period,age_minutes):
    logging.info(" \n\n\n\n\n  Deleting Snapshot.... \n\n\n\n\n\n ")
    compute_client.snapshots.begin_delete(resource_group_name,snapshot_name=snapshotName,)
    logging.info(f" \n\n\n\n\n  SNAPSHOT HAS BEEN DELETED {snapshotName} !! \n\n\n\n\n\n ")
    send_deletion_email(created_by, snapshotName, creation_date, retention_period, age_minutes)

def send_mail(created_by, email_body):

    sender_email = ' '
    sender_password = ' '       # On your gmail account, enable 2 factor authentication and create an app password, copy and paste it here.

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, created_by, email_body)
    server.quit()

    logging.info(' \n\n\n\n\n\n\n\n\n\n\n   MAIL HAS BEEN SENT !! !! !!  \n\n\n\n\n\n\n\n\n\n\n ')


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

    Best regards,
    Azure Team
    """
    send_mail(created_by, email_body)


def notify(created_by, snapshot_name, creation_date, retention_period, age_minutes):
    email_body = f"""
    Hello,

    The snapshot '{snapshot_name}', created on {creation_date.strftime('%Y-%m-%d')}, is still available since 3 months.
    Please check it and update it's retention period tag.


    Snapshot Details:
    - Name: {snapshot_name}
    - Creation Date: {creation_date.strftime('%Y-%m-%d')}
    - Creation Time: {creation_date.strftime('%H:%M:%S')}
    - Retention Period: {retention_period} minutes
    - Snapshot Age: {age_minutes} minutes

    Best regards,
    Azure Team
    """
    send_mail(created_by, email_body)
