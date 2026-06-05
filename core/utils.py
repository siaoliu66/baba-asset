from datetime import datetime
from flask import request
from core.models.system import AuditLog, Notification
from extensions import db, socketio

class SystemHelper:
    @staticmethod
    def log_event(user_id, module, action, description, old_value=None, new_value=None, reference_id=None):
        log = AuditLog(
            user_id=user_id,
            module=module,
            action=action,
            description=description,
            old_value=old_value,
            new_value=new_value,
            reference_id=str(reference_id) if reference_id else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string if request else None
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def send_notification(user_id, n_type, title, content, link=None):
        notify = Notification(
            user_id=user_id,
            type=n_type,
            title=title,
            content=content,
            link=link
        )
        db.session.add(notify)
        db.session.commit()
        
        # Real-time push via SocketIO
        socketio.emit(f'notification_user_{user_id}', {
            'id': notify.id,
            'title': title,
            'content': content,
            'created_at': notify.created_at.strftime('%Y-%m-%d %H:%M')
        })
        return notify

    @staticmethod
    def handle_rejection(reference_type, reference_id, comment, rejected_by):
        """
        When rejected: Status resets to draft.
        """
        # Specific logic based on reference_type
        # (e.g. for Transfer or InventoryPlan)
        pass
