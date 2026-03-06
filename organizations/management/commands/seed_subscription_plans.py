from decimal import Decimal

from django.core.management.base import BaseCommand

from organizations.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Seed/update Elevo subscription plans for Week 1 B2B packaging."

    def handle(self, *args, **options):
        plans = [
            {
                "name": "STARTER",
                "target_type": "ORGANIZATION",
                "display_name": "Starter",
                "description": "Best for a single batch beginning placement prep.",
                "price_monthly": Decimal("14999.00"),
                "max_students": 120,
                "max_problems": 250,
                "max_aptitude_daily": 5,
                "max_interviews_monthly": 3,
                "has_editorials": True,
                "has_detailed_analytics": False,
                "has_custom_branding": False,
                "has_priority_support": False,
                "is_active": True,
            },
            {
                "name": "GROWTH",
                "target_type": "ORGANIZATION",
                "display_name": "Growth",
                "description": "For institutions running multiple active training batches.",
                "price_monthly": Decimal("39999.00"),
                "max_students": 500,
                "max_problems": -1,
                "max_aptitude_daily": -1,
                "max_interviews_monthly": 10,
                "has_editorials": True,
                "has_detailed_analytics": True,
                "has_custom_branding": True,
                "has_priority_support": False,
                "is_active": True,
            },
            {
                "name": "ENTERPRISE",
                "target_type": "ORGANIZATION",
                "display_name": "Enterprise",
                "description": "For large organizations needing scale, analytics, and support.",
                "price_monthly": Decimal("99999.00"),
                "max_students": -1,
                "max_problems": -1,
                "max_aptitude_daily": -1,
                "max_interviews_monthly": -1,
                "has_editorials": True,
                "has_detailed_analytics": True,
                "has_custom_branding": True,
                "has_priority_support": True,
                "is_active": True,
            },
            {
                "name": "FREE",
                "target_type": "ORGANIZATION",
                "display_name": "Free Trial",
                "description": "Evaluation plan for trial onboarding.",
                "price_monthly": Decimal("0.00"),
                "max_students": 10,
                "max_problems": 20,
                "max_aptitude_daily": 1,
                "max_interviews_monthly": 0,
                "has_editorials": False,
                "has_detailed_analytics": False,
                "has_custom_branding": False,
                "has_priority_support": False,
                "is_active": True,
            },
            {
                "name": "PERSONAL_PRO",
                "target_type": "INDIVIDUAL",
                "display_name": "Personal Pro",
                "description": "Unlimited self-prep for individual learners.",
                "price_monthly": Decimal("499.00"),
                "max_students": 1,
                "max_problems": -1,
                "max_aptitude_daily": -1,
                "max_interviews_monthly": 10,
                "has_editorials": True,
                "has_detailed_analytics": False,
                "has_custom_branding": False,
                "has_priority_support": False,
                "is_active": True,
            },
        ]

        for payload in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=payload["name"],
                defaults=payload,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action}: {plan.name}"))

        self.stdout.write(self.style.SUCCESS("Subscription plans seeded successfully."))
