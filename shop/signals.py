from django.db.models.signals import post_save
from django.dispatch import receiver

from shop.models import Appointment, Sale
from shop.services.loyalty import award_points_for_completed_appointment, award_points_for_sale


@receiver(post_save, sender=Appointment)
def loyalty_on_appointment_completed(sender, instance, **kwargs):
    if instance.status == Appointment.Status.COMPLETED:
        award_points_for_completed_appointment(instance)


@receiver(post_save, sender=Sale)
def loyalty_on_sale(sender, instance, **kwargs):
    award_points_for_sale(instance)
