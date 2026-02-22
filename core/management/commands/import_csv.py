import csv
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Topic, Lesson, Quiz, Question, Option, Article, CodeSnippet
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Import full Elevo data from CSV'

    def handle(self, *args, **kwargs):
        csv_file = 'elevo_content.csv' if os.path.exists('elevo_content.csv') else 'elevo_content.csv'
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                topic, _ = Topic.objects.get_or_create(
                    name=row['topic_name'],
                    slug=row['topic_slug'],
                    defaults={'description': row['topic_description']}
                )

                lesson = Lesson.objects.create(
                    topic=topic,
                    title=row['lesson_title'],
                    content=row['lesson_content'],
                    order=row['lesson_order']
                )

                quiz, _ = Quiz.objects.get_or_create(topic=topic, defaults={'title': f'{topic.name} Quiz'})
                question = Question.objects.create(
                    quiz=quiz,
                    question_text=row['question_text'],
                    explanation=row['explanation']
                )

                # Add options
                for i in range(1, 5):
                    text = row[f'option_{i}']
                    is_correct = (i == int(row['correct_option']))
                    Option.objects.create(question=question, text=text, is_correct=is_correct)

                # Add code snippets
                CodeSnippet.objects.create(lesson=lesson, language=row['code_lang_1'], code=row['code_1'])
                CodeSnippet.objects.create(lesson=lesson, language=row['code_lang_2'], code=row['code_2'])
                CodeSnippet.objects.create(lesson=lesson, language=row['code_lang_3'], code=row['code_3'])

                # Add article
                author = User.objects.filter(is_superuser=True).first()
                article = Article.objects.create(
                    title=row['article_title'],
                    slug=slugify(row['article_title']),
                    category=row['article_category'],
                    content=row['article_content'],
                    author=author
                )

        self.stdout.write(self.style.SUCCESS("✅ Data imported successfully!"))
