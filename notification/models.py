from django.db import models
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
import logging

logger = logging.getLogger(__name__)


class NotificationIssue(models.Model):
    """
    Model representing an issue that requires notification-based approval workflow.

    This model encapsulates an action that needs to be approved through a notification
    system before execution. It manages the mapping of action methods and their
    execution logic based on notification responses.
    """

    method_mapping = {
        "chgsp": 'dummymethod1',
        "chglb": 'dummymethod2',
        "dummymethod3": 'dummymethod3',
    }

    method = models.CharField(_('Действие'), max_length=5)
    kwargs = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name=_('Параметры')
    )

    @property
    def is_action_allowed(self):
        """
        Determine if the action is allowed based on notification responses.

        Evaluates the approval status by checking related notifications against
        logical dependencies (AND/OR). For AND logic, requires no rejections or
        pending notifications. For OR logic, requires at least one acceptance.

        Returns:
            bool: True if action is allowed, False otherwise.
        """
        notification_relations = self.issue_notifications.prefetch_related(
            'pending_notifications',
            'accepted_notifications',
            'rejected_notifications'
        ).filter(is_active=True)

        for notification_relation in notification_relations:
            if notification_relation.logic_dependence == '&':  # нарушил инкапсуляцию ради оптимизации запросов, возможно тут в этом нет необходимости и можно вернуть
                has_rejected = bool(notification_relation.rejected_notifications.all())
                has_pending = bool(notification_relation.pending_notifications.all())
                if has_rejected or has_pending:
                    return False
            elif notification_relation.logic_dependence == '|':
                has_accepted = bool(notification_relation.accepted_notifications.all())
                if not has_accepted:
                    return False
        return True

    def try_action(self) -> bool:
        """
        Attempt to execute the action if all notification conditions are met.

        Validates approval status, maps the method code to actual method,
        and executes with provided kwargs. Logs errors for missing methods
        or execution failures.

        Returns:
            bool: True if action was successfully executed, False otherwise.
        """
        if not self.is_action_allowed:
            return False

        method_name = self.method_mapping.get(self.method)
        if not method_name:
            logger.warning(f"Unknown action {self.method}")
            return False

        method = getattr(self, method_name, None)
        if method is None or not callable(method):
            logger.error(f"Method {method_name} not implemented on {self.__class__.__name__}")
            return False

        try:
            method(**self.kwargs)
        except Exception as exc:
            logger.exception(f"Error executing {method_name}: {exc}")
            return False
        else:
            return True


class NotificationRelations(models.Model):
    """
    Model defining the relationship between notification issues and their responses.

    This model establishes logical dependencies (AND/OR) for notification approval
    and tracks the active status of the approval workflow.

    Attributes:
        LOGIC_DEPENDENCE_CHOICES (tuple): Available logic types for approval.
        logic_dependence (str): Logical operator for evaluating notifications.
        is_active (bool): Indicates if the approval workflow is currently active.
        issue (ForeignKey): Related NotificationIssue requiring approval.
    """

    LOGIC_DEPENDENCE_CHOICES = (
        ('&', _('Логика И')),
        ('|', _('Логика ИЛИ')),
    )
    logic_dependence = models.CharField(
        _('Логика Согласования'),
        max_length=1,
        choices=LOGIC_DEPENDENCE_CHOICES,
        default=LOGIC_DEPENDENCE_CHOICES[0][0],
    )
    is_active = models.BooleanField(
        _('Предложение активно'),
        default=False,
    )
    issue = models.ForeignKey(
        NotificationIssue,
        verbose_name=_('Notification issue'),
        on_delete=models.PROTECT,
        related_name='issue_notifications'
    )


    class Meta:
        """
        Metadata class for NotificationRelations model.

        Defines database indexes for improved query performance on frequently
        accessed fields.
        """
        indexes = [
            models.Index(fields=['logic_dependence']),
            models.Index(fields=['is_active']),
            models.Index(fields=['issue']),
        ]


class Notification(models.Model):
    """
    Base model for all notification types in the approval workflow.

    Represents a message sent from one user to another as part of an approval
    process. This abstract model is extended by specific notification status types.
    """

    user_from = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='notifications_sent',
        verbose_name=_('Отправитель')
    )
    user_to = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='notifications_received',
        verbose_name=_('Получатель')
    )
    date_created = models.DateTimeField(auto_now_add=True)
    message = models.TextField(_('Письмо уведомление'))


class PendingNotification(Notification):
    """
    Model representing notifications that are awaiting a response.

    Extends the base Notification model to track notifications that have been
    sent but not yet accepted or rejected. Links to NotificationRelations for
    approval workflow tracking.
    """

    notification_relations = models.ForeignKey(NotificationRelations, on_delete=models.PROTECT, blank=True, null=True,
                                               related_name='pending_notifications')

    class Meta:
        """
        Metadata class for PendingNotification model.

        Defines database indexes for improved query performance.
        """
        indexes = [models.Index(fields=['notification_relations'])]


class AcceptedNotification(Notification):
    """
    Model representing notifications that have been accepted by the recipient.

    Extends the base Notification model to track accepted notifications with
    timestamp of acceptance. Links to NotificationRelations for approval workflow.
    """

    notification_relations = models.ForeignKey(NotificationRelations, on_delete=models.PROTECT, blank=True, null=True,
                                               related_name='accepted_notifications')
    accept_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadata class for AcceptedNotification model.

        Defines database indexes for improved query performance.
        """
        indexes = [models.Index(fields=['notification_relations'])]


class RejectedNotification(Notification):
    """
    Model representing notifications that have been rejected by the recipient.

    Extends the base Notification model to track rejected notifications with
    timestamp of rejection. Links to NotificationRelations for approval workflow.
    """

    notification_relations = models.ForeignKey(NotificationRelations, on_delete=models.PROTECT, blank=True, null=True,
                                               related_name='rejected_notifications')
    reject_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadata class for RejectedNotification model.

        Defines database indexes for improved query performance.
        """
        indexes = [models.Index(fields=['notification_relations'])]