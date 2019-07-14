from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django_populate import Faker


class Command(BaseCommand):
    help = "Evaluate a tournament in round-robin mode."

    def handle(self, *args, **options):
        User = get_user_model()
        populator = Faker.getPopulator()
        populator.addEntity(User, 20)
        populator.execute()
