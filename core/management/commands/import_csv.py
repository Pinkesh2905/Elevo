import csv
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from core.models import Topic, Lesson, Quiz, Question, Option, Article, CodeSnippet


class Command(BaseCommand):
    help = 'Import full Elevo data from CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            default=os.getenv('ELEVO_CONTENT_CSV', 'elevo_content.csv'),
            help='Path to content CSV (default: ELEVO_CONTENT_CSV or elevo_content.csv)',
        )

    def handle(self, *args, **options):
        csv_file = self._resolve_csv_path(options['csv_file'])
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file not found: {csv_file}')

        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                topic, _ = Topic.objects.get_or_create(
                    name=row['topic_name'],
                    slug=row['topic_slug'],
                    defaults={'description': row['topic_description']},
                )

                lesson = Lesson.objects.create(
                    topic=topic,
                    title=row['lesson_title'],
                    content=row['lesson_content'],
                    order=row['lesson_order'],
                )

                quiz, _ = Quiz.objects.get_or_create(topic=topic, defaults={'title': f'{topic.name} Quiz'})
                question = Question.objects.create(
                    quiz=quiz,
                    question_text=row['question_text'],
                    explanation=row['explanation'],
                )

                for idx in range(1, 5):
                    text = row[f'option_{idx}']
                    is_correct = idx == int(row['correct_option'])
                    Option.objects.create(question=question, text=text, is_correct=is_correct)

                CodeSnippet.objects.create(lesson=lesson, language=row['code_lang_1'], code=row['code_1'])
                CodeSnippet.objects.create(lesson=lesson, language=row['code_lang_2'], code=row['code_2'])
                CodeSnippet.objects.create(lesson=lesson, language=row['code_lang_3'], code=row['code_3'])

                author = User.objects.filter(is_superuser=True).first()
                Article.objects.create(
                    title=row['article_title'],
                    slug=slugify(row['article_title']),
                    category=row['article_category'],
                    content=row['article_content'],
                    author=author,
                )

        self.stdout.write(self.style.SUCCESS('Data imported successfully'))

    def _resolve_csv_path(self, csv_file):
        if os.path.exists(csv_file):
            return csv_file

        if csv_file.endswith('.csv'):
            sample_csv = f"{csv_file[:-4]}_sample.csv"
            if os.path.exists(sample_csv):
                self.stdout.write(self.style.WARNING(f'Using sample CSV: {sample_csv}'))
                return sample_csv

        return csv_file
