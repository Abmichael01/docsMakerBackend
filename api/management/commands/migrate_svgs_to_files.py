from django.core.management.base import BaseCommand
from api.models import Template, PurchasedTemplate
from django.core.files.base import ContentFile
from django.db import transaction
import time

class Command(BaseCommand):
    help = 'Migrates SVG text content to FileField'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the migration without saving changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}Starting migration of SVGs to files...')
        
        # 1. Templates
        templates = Template.objects.all()
        t_count = templates.count()
        self.stdout.write(f'Found {t_count} templates to process.')
        
        migrated_t = 0
        skipped_t = 0
        
        for t in templates:
            try:
                if t.svg_file and t.svg_file.name:
                    skipped_t += 1
                    continue
                if not t.svg:
                    skipped_t += 1
                    continue
                
                filename = f"{t.id}.svg"
                file_content = ContentFile(t.svg.encode('utf-8'))
                
                if not dry_run:
                    # save=True here saves the model instance too, unless we pass save=False
                    # But we want to update the row.
                    t.svg_file.save(filename, file_content, save=True)
                
                migrated_t += 1
                if migrated_t % 10 == 0:
                    self.stdout.write(f'Processed {migrated_t} templates...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing Template {t.id}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(
            f'Templates: {migrated_t} migrated, {skipped_t} skipped.'
        ))

        # 2. Purchased Templates
        purchased = PurchasedTemplate.objects.all()
        p_count = purchased.count()
        self.stdout.write(f'Found {p_count} purchased templates to process.')
        
        migrated_p = 0
        skipped_p = 0
        
        for p in purchased:
            try:
                if p.svg_file and p.svg_file.name:
                    skipped_p += 1
                    continue
                if not p.svg:
                    skipped_p += 1
                    continue
                
                filename = f"{p.id}.svg"
                file_content = ContentFile(p.svg.encode('utf-8'))
                
                if not dry_run:
                    p.svg_file.save(filename, file_content, save=True)
                
                migrated_p += 1
                if migrated_p % 10 == 0:
                    self.stdout.write(f'Processed {migrated_p} purchased templates...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing PurchasedTemplate {p.id}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(
            f'PurchasedTemplates: {migrated_p} migrated, {skipped_p} skipped.'
        ))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("This was a dry run. No changes were committed."))
        else:
            self.stdout.write(self.style.SUCCESS("Migration complete."))
