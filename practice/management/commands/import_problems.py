"""
Management command to import practice app data from CSV files

Place this file at: practice/management/commands/import_problems.py

Usage:
    python manage.py import_problems --data-dir /path/to/csv/files
    python manage.py import_problems --data-dir ./practice_data --clear
"""

import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from practice.models import (
    Topic, Company, Problem, TestCase, 
    CodeTemplate, Editorial
)


class Command(BaseCommand):
    help = 'Import problems, test cases, and templates from CSV files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            default='practice_data',
            help='Directory containing CSV files (default: practice_data)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before importing'
        )
        parser.add_argument(
            '--user',
            type=str,
            default='admin',
            help='Username for created_by field (default: admin)'
        )

    def handle(self, *args, **options):
        data_dir = options['data_dir']
        clear_data = options['clear']
        username = options['user']

        # Check if directory exists
        if not os.path.isdir(data_dir):
            raise CommandError(f'Directory "{data_dir}" does not exist')

        # Get or create user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'User "{username}" not found. Using None for created_by.')
            )
            user = None

        # Clear existing data if requested
        if clear_data:
            self.stdout.write(self.style.WARNING('Clearing existing data...'))
            Editorial.objects.all().delete()
            CodeTemplate.objects.all().delete()
            TestCase.objects.all().delete()
            Problem.objects.all().delete()
            Company.objects.all().delete()
            Topic.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Data cleared'))

        # Import in order of dependencies
        self.import_topics(data_dir)
        self.import_companies(data_dir)
        self.import_problems(data_dir, user)
        self.import_test_cases(data_dir)
        self.import_code_templates(data_dir)
        self.import_editorials(data_dir)
 
        self.stdout.write(self.style.SUCCESS('\n🎉 Import completed successfully!'))

    def import_topics(self, data_dir):
        """Import topics from topics.csv"""
        csv_path = os.path.join(data_dir, 'topics.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING(f'⚠ Skipping topics: {csv_path} not found'))
            return

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                Topic.objects.get_or_create(
                    name=row['name'],
                    defaults={
                        'slug': row.get('slug', ''),
                        'description': row.get('description', ''),
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f'✓ Imported {count} topics'))

    def import_companies(self, data_dir):
        """Import companies from companies.csv"""
        csv_path = os.path.join(data_dir, 'companies.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING(f'⚠ Skipping companies: {csv_path} not found'))
            return

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                Company.objects.get_or_create(
                    name=row['name'],
                    defaults={
                        'slug': row.get('slug', ''),
                        'website': row.get('website', ''),
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f'✓ Imported {count} companies'))

    def import_problems(self, data_dir, user):
        """Import problems from problems.csv"""
        csv_path = os.path.join(data_dir, 'problems.csv')
        
        if not os.path.exists(csv_path):
            raise CommandError(f'Required file not found: {csv_path}')

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                # Create or update problem
                problem, created = Problem.objects.update_or_create(
                    problem_number=int(row['problem_number']),
                    defaults={
                        'title': row['title'],
                        'difficulty': row.get('difficulty', 'medium').lower(),
                        'description': row.get('description', ''),
                        'constraints': row.get('constraints', ''),
                        'example_input': row.get('example_input', ''),
                        'example_output': row.get('example_output', ''),
                        'example_explanation': row.get('example_explanation', ''),
                        'hints': row.get('hints', ''),
                        'time_complexity': row.get('time_complexity', ''),
                        'space_complexity': row.get('space_complexity', ''),
                        'created_by': user,
                        'is_active': row.get('is_active', 'true').lower() == 'true',
                    }
                )

                # Add topics (comma-separated)
                if row.get('topics'):
                    topic_names = [t.strip() for t in row['topics'].split(',')]
                    topics = Topic.objects.filter(name__in=topic_names)
                    problem.topics.set(topics)

                # Add companies (comma-separated)
                if row.get('companies'):
                    company_names = [c.strip() for c in row['companies'].split(',')]
                    companies = Company.objects.filter(name__in=company_names)
                    problem.companies.set(companies)

                count += 1
                action = 'Created' if created else 'Updated'
                self.stdout.write(f'  {action}: Problem #{problem.problem_number} - {problem.title}')

        self.stdout.write(self.style.SUCCESS(f'✓ Imported {count} problems'))

    def import_test_cases(self, data_dir):
        """Import test cases from test_cases.csv"""
        csv_path = os.path.join(data_dir, 'test_cases.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING(f'⚠ Skipping test cases: {csv_path} not found'))
            return

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                try:
                    problem = Problem.objects.get(problem_number=int(row['problem_number']))
                    
                    TestCase.objects.create(
                        problem=problem,
                        input_data=row['input_data'],
                        expected_output=row['expected_output'],
                        is_sample=row.get('is_sample', 'false').lower() == 'true',
                        explanation=row.get('explanation', ''),
                        order=int(row.get('order', count)),
                    )
                    count += 1
                except Problem.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'  Problem #{row["problem_number"]} not found for test case')
                    )

        self.stdout.write(self.style.SUCCESS(f'✓ Imported {count} test cases'))

    def import_code_templates(self, data_dir):
        """Import code templates from code_templates.csv"""
        csv_path = os.path.join(data_dir, 'code_templates.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING(f'⚠ Skipping code templates: {csv_path} not found'))
            return

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                try:
                    problem = Problem.objects.get(problem_number=int(row['problem_number']))
                    
                    CodeTemplate.objects.update_or_create(
                        problem=problem,
                        language=row['language'],
                        defaults={
                            'template_code': row.get('template_code', ''),
                            'solution_code': row.get('solution_code', ''),
                        }
                    )
                    count += 1
                except Problem.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'  Problem #{row["problem_number"]} not found for template')
                    )

        self.stdout.write(self.style.SUCCESS(f'✓ Imported {count} code templates'))

    def import_editorials(self, data_dir):
        """Import editorials from editorials.csv"""
        csv_path = os.path.join(data_dir, 'editorials.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING(f'⚠ Skipping editorials: {csv_path} not found'))
            return

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            count = 0
            
            for row in reader:
                try:
                    problem = Problem.objects.get(problem_number=int(row['problem_number']))
                    
                    Editorial.objects.update_or_create(
                        problem=problem,
                        defaults={
                            'approach': row.get('approach', ''),
                            'complexity_analysis': row.get('complexity_analysis', ''),
                            'code_explanation': row.get('code_explanation', ''),
                            'video_url': row.get('video_url', ''),
                        }
                    )
                    count += 1
                except Problem.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'  Problem #{row["problem_number"]} not found for editorial')
                    )

        self.stdout.write(self.style.SUCCESS(f'✓ Imported {count} editorials'))