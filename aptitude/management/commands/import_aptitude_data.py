import csv
import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.termcolors import make_style

from aptitude.models import AptitudeCategory, AptitudeTopic, AptitudeProblem, PracticeSet


class Command(BaseCommand):
    help = 'Import aptitude data from CSV files'

    def __init__(self):
        super().__init__()
        self.success = make_style(opts=('bold',), fg='green')
        self.error = make_style(opts=('bold',), fg='red')
        self.warning = make_style(opts=('bold',), fg='yellow')

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            default=os.getenv('APTITUDE_DATA_DIR', 'data'),
            help='Directory containing CSV files (default: APTITUDE_DATA_DIR or data)',
        )
        parser.add_argument('--categories', type=str, default='categories.csv', help='Categories CSV filename')
        parser.add_argument('--topics', type=str, default='topics.csv', help='Topics CSV filename')
        parser.add_argument('--problems', type=str, default='problems.csv', help='Problems CSV filename')
        parser.add_argument(
            '--practice-sets',
            type=str,
            default='practice_sets.csv',
            help='Practice sets CSV filename',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing data before import',
        )

    def handle(self, *args, **options):
        data_dir = options['data_dir']

        if not os.path.exists(data_dir):
            self.stdout.write(self.error(f'Data directory "{data_dir}" does not exist'))
            return

        if options['clear_existing']:
            self.clear_existing_data()

        try:
            with transaction.atomic():
                categories_file = self._resolve_csv_path(data_dir, options['categories'])
                topics_file = self._resolve_csv_path(data_dir, options['topics'])
                problems_file = self._resolve_csv_path(data_dir, options['problems'])
                practice_sets_file = self._resolve_csv_path(data_dir, options['practice_sets'])

                self.import_categories(categories_file)
                self.import_topics(topics_file)
                self.import_problems(problems_file)
                self.import_practice_sets(practice_sets_file)

                self.stdout.write(self.success('\nAll aptitude data imported successfully'))

        except Exception as exc:
            self.stdout.write(self.error(f'\nImport failed: {exc}'))
            raise

    def _resolve_csv_path(self, data_dir, filename):
        csv_path = os.path.join(data_dir, filename)
        if os.path.exists(csv_path):
            return csv_path

        if filename.endswith('.csv'):
            sample_filename = f"{filename[:-4]}_sample.csv"
            sample_csv_path = os.path.join(data_dir, sample_filename)
            if os.path.exists(sample_csv_path):
                self.stdout.write(self.warning(f'Using sample CSV: {sample_csv_path}'))
                return sample_csv_path

        return csv_path

    def clear_existing_data(self):
        self.stdout.write(self.warning('Clearing existing aptitude data...'))

        AptitudeProblem.objects.all().delete()
        AptitudeTopic.objects.all().delete()
        AptitudeCategory.objects.all().delete()
        PracticeSet.objects.all().delete()

        self.stdout.write(self.success('Existing aptitude data cleared'))

    def import_categories(self, file_path):
        if not os.path.exists(file_path):
            self.stdout.write(self.warning(f'Categories file not found: {file_path}'))
            return

        self.stdout.write('Importing categories...')

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            categories_created = 0
            categories_updated = 0

            for row in reader:
                category, created = AptitudeCategory.objects.get_or_create(
                    name=row['name'],
                    defaults={'description': row.get('description', '')},
                )

                if created:
                    categories_created += 1
                elif row.get('description') and category.description != row['description']:
                    category.description = row['description']
                    category.save()
                    categories_updated += 1

        self.stdout.write(
            self.success(
                f'Categories: {categories_created} created, {categories_updated} updated'
            )
        )

    def import_topics(self, file_path):
        if not os.path.exists(file_path):
            self.stdout.write(self.warning(f'Topics file not found: {file_path}'))
            return

        self.stdout.write('Importing topics...')

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            topics_created = 0
            topics_skipped = 0

            for row in reader:
                try:
                    category = AptitudeCategory.objects.get(name=row['category_name'])
                    topic, created = AptitudeTopic.objects.get_or_create(
                        category=category,
                        name=row['name'],
                        defaults={'description': row.get('description', '')},
                    )

                    if created:
                        topics_created += 1
                    elif row.get('description') and topic.description != row['description']:
                        topic.description = row['description']
                        topic.save()

                except AptitudeCategory.DoesNotExist:
                    self.stdout.write(
                        self.error(
                            f'Category not found: {row["category_name"]} for topic: {row["name"]}'
                        )
                    )
                    topics_skipped += 1

        self.stdout.write(self.success(f'Topics: {topics_created} created, {topics_skipped} skipped'))

    def import_problems(self, file_path):
        if not os.path.exists(file_path):
            self.stdout.write(self.warning(f'Problems file not found: {file_path}'))
            return

        self.stdout.write('Importing problems...')

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            problems_created = 0
            problems_skipped = 0

            for row_num, row in enumerate(reader, start=2):
                try:
                    required_fields = [
                        'category_name',
                        'topic_name',
                        'question_text',
                        'option_a',
                        'option_b',
                        'option_c',
                        'option_d',
                        'correct_option',
                    ]
                    missing_fields = [field for field in required_fields if not row.get(field)]
                    if missing_fields:
                        self.stdout.write(
                            self.error(f'Row {row_num}: Missing fields: {", ".join(missing_fields)}')
                        )
                        problems_skipped += 1
                        continue

                    if row['correct_option'].upper() not in ['A', 'B', 'C', 'D']:
                        self.stdout.write(
                            self.error(
                                f'Row {row_num}: Invalid correct_option: {row["correct_option"]}'
                            )
                        )
                        problems_skipped += 1
                        continue

                    topic = AptitudeTopic.objects.get(
                        name=row['topic_name'],
                        category__name=row['category_name'],
                    )

                    AptitudeProblem.objects.create(
                        topic=topic,
                        question_text=row['question_text'].strip(),
                        option_a=row['option_a'].strip(),
                        option_b=row['option_b'].strip(),
                        option_c=row['option_c'].strip(),
                        option_d=row['option_d'].strip(),
                        correct_option=row['correct_option'].upper(),
                        explanation=row.get('explanation', '').strip(),
                        difficulty=row.get('difficulty', 'Medium'),
                    )
                    problems_created += 1

                except AptitudeTopic.DoesNotExist:
                    self.stdout.write(
                        self.error(
                            f'Row {row_num}: Topic not found: {row["topic_name"]} in {row["category_name"]}'
                        )
                    )
                    problems_skipped += 1
                except Exception as exc:
                    self.stdout.write(self.error(f'Row {row_num}: Error creating problem: {exc}'))
                    problems_skipped += 1

        self.stdout.write(
            self.success(f'Problems: {problems_created} created, {problems_skipped} skipped')
        )

    def import_practice_sets(self, file_path):
        if not os.path.exists(file_path):
            self.stdout.write(self.warning(f'Practice sets file not found: {file_path}'))
            return

        self.stdout.write('Importing practice sets...')

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            sets_created = 0
            sets_skipped = 0

            for row in reader:
                try:
                    practice_set = PracticeSet.objects.create(
                        title=row['title'],
                        description=row.get('description', ''),
                        created_by=None,
                    )

                    if row.get('problem_ids'):
                        try:
                            problem_ids = [
                                int(problem_id.strip())
                                for problem_id in row['problem_ids'].split(',')
                                if problem_id.strip()
                            ]
                            problems = AptitudeProblem.objects.filter(id__in=problem_ids)

                            if problems.exists():
                                practice_set.problems.set(problems)
                                sets_created += 1
                            else:
                                self.stdout.write(
                                    self.error(
                                        f'No valid problems found for practice set: {row["title"]}'
                                    )
                                )
                                practice_set.delete()
                                sets_skipped += 1
                        except ValueError:
                            self.stdout.write(
                                self.error(
                                    f'Invalid problem IDs for practice set: {row["title"]}'
                                )
                            )
                            practice_set.delete()
                            sets_skipped += 1
                    else:
                        sets_created += 1

                except Exception as exc:
                    self.stdout.write(
                        self.error(
                            f'Error creating practice set "{row.get("title", "Unknown")}": {exc}'
                        )
                    )
                    sets_skipped += 1

        self.stdout.write(self.success(f'Practice sets: {sets_created} created, {sets_skipped} skipped'))
