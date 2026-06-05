from datetime import datetime, timedelta
from extensions import db, scheduler
from core.models.documents import Document
from core.models.workflow import ApprovalRecord
from core.utils import SystemHelper

def check_contract_expiry():
    """
    Check for contracts expiring in the next 'reminder_days'.
    """
    # This runs within app context if started via scheduler.init_app(app)
    with scheduler.app.app_context():
        today = datetime.now().date()
        # Find active contracts that haven't been notified today
        expiring_docs = Document.query.filter(
            Document.is_contract == True,
            Document.status == 'active',
            Document.contract_end_date <= today + timedelta(days=30) # Default 30 days
        ).all()
        
        for doc in expiring_docs:
            days_left = (doc.contract_end_date - today).days
            if days_left >= 0:
                SystemHelper.send_notification(
                    user_id=doc.owner_id,
                    n_type='contract_alert',
                    title=f'合約到期提醒: {doc.title}',
                    content=f'文件編號 {doc.doc_number} 將於 {days_left} 天後到期 ({doc.contract_end_date})，請儘速處理續約或結案。',
                    link=f'/documents/view/{doc.id}'
                )
        print(f"[{datetime.now()}] Ran check_contract_expiry: {len(expiring_docs)} alerts sent.")

def check_approval_reminders():
    """
    Find pending approvals and send reminders if they exceed the threshold.
    """
    with scheduler.app.app_context():
        # Find records pending for more than APPROVAL_REMINDER_DAYS
        # (Simplified: assume 3 days)
        threshold = datetime.utcnow() - timedelta(days=3)
        pending_records = ApprovalRecord.query.filter(
            ApprovalRecord.status == 'pending',
            ApprovalRecord.reminded_at == None # Or older than 24h
        ).all()
        
        for record in pending_records:
            SystemHelper.send_notification(
                user_id=record.selected_approver_id,
                n_type='approval_reminder',
                title='簽核催辦提醒',
                content=f'您有一項編號 #{record.reference_id} 的 {record.reference_type} 申請尚未處理，請儘速核閱。',
                link='/workflows/requests'
            )
            record.reminded_count += 1
            record.reminded_at = datetime.utcnow()
        
        db.session.commit()
        print(f"[{datetime.now()}] Ran check_approval_reminders: {len(pending_records)} reminders sent.")

def run_monthly_depreciation():
    """
    Run monthly depreciation for the previous month.
    Scheduled for 1st day of every month.
    """
    with scheduler.app.app_context():
        # Calculate for previous month
        today = datetime.now()
        first = today.replace(day=1)
        last_month = first - timedelta(days=1)
        
        year = last_month.year
        month = last_month.month
        
        from modules.finance.services import DepreciationService
        count = DepreciationService.run_monthly_closing(year, month)
        print(f"[{datetime.now()}] Ran run_monthly_depreciation for {year}-{month}: {count} records created.")

def init_scheduled_tasks(app):
    """
    Register recurring jobs.
    """
    # Every day at 09:00 AM
    scheduler.add_job(
        id='contract_expiry_job',
        func=check_contract_expiry,
        trigger='cron',
        hour=9,
        minute=0
    )
    
    # Every 4 hours for approval reminders
    scheduler.add_job(
        id='approval_reminder_job',
        func=check_approval_reminders,
        trigger='interval',
        hours=4
    )
    
    # Monthly Depreciation (1st day of month at 01:00 AM)
    scheduler.add_job(
        id='monthly_depreciation_job',
        func=run_monthly_depreciation,
        trigger='cron',
        day=1,
        hour=1,
        minute=0
    )
