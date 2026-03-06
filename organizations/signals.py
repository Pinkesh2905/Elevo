from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from organizations.models import Membership, OrganizationAuditLog, Subscription


@receiver(pre_save, sender=Membership)
def capture_membership_previous_role(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_role = None
        return
    previous = Membership.objects.filter(pk=instance.pk).values("role").first()
    instance._previous_role = previous["role"] if previous else None


@receiver(post_save, sender=Membership)
def audit_membership_role_change(sender, instance, created, **kwargs):
    if created:
        return
    previous_role = getattr(instance, "_previous_role", None)
    if previous_role and previous_role != instance.role:
        OrganizationAuditLog.objects.create(
            organization=instance.organization,
            actor=instance.invited_by,
            target_user=instance.user,
            action="MEMBERSHIP_ROLE_CHANGED",
            details={"from": previous_role, "to": instance.role},
        )


@receiver(pre_save, sender=Subscription)
def capture_subscription_previous_plan(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_plan_id = None
        return
    previous = Subscription.objects.filter(pk=instance.pk).values("plan_id").first()
    instance._previous_plan_id = previous["plan_id"] if previous else None


@receiver(post_save, sender=Subscription)
def audit_subscription_events(sender, instance, created, **kwargs):
    if created:
        OrganizationAuditLog.objects.create(
            organization=instance.organization,
            actor=instance.organization.admin if instance.organization else instance.user,
            target_user=instance.user,
            action="SUBSCRIPTION_CREATED",
            details={
                "plan": instance.plan.name,
                "target_type": "organization" if instance.organization else "individual",
            },
        )
        return

    previous_plan_id = getattr(instance, "_previous_plan_id", None)
    if previous_plan_id and previous_plan_id != instance.plan_id:
        OrganizationAuditLog.objects.create(
            organization=instance.organization,
            actor=instance.organization.admin if instance.organization else instance.user,
            target_user=instance.user,
            action="SUBSCRIPTION_PLAN_CHANGED",
            details={"from_plan_id": previous_plan_id, "to_plan_id": instance.plan_id},
        )
