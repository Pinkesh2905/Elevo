"""
Management command to populate database with sample problems
Usage: python manage.py populate_problems
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from practice.models import (
    Topic, Company, Problem, CodeTemplate, TestCase
)


class Command(BaseCommand):
    help = 'Populate database with sample coding problems'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing problems before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            Problem.objects.all().delete()
            Topic.objects.all().delete()
            Company.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Data cleared!'))

        # Create admin user if doesn't exist
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@elevo.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Admin user created!'))

        # Create Topics
        self.stdout.write('Creating topics...')
        topics_data = [
            {'name': 'Array', 'icon': '📊'},
            {'name': 'String', 'icon': '📝'},
            {'name': 'Hash Table', 'icon': '🔑'},
            {'name': 'Dynamic Programming', 'icon': '💡'},
            {'name': 'Math', 'icon': '🔢'},
            {'name': 'Sorting', 'icon': '🔄'},
            {'name': 'Greedy', 'icon': '🎯'},
            {'name': 'Binary Search', 'icon': '🔍'},
            {'name': 'Tree', 'icon': '🌳'},
            {'name': 'Graph', 'icon': '🕸️'},
            {'name': 'Stack', 'icon': '📚'},
            {'name': 'Queue', 'icon': '🎫'},
            {'name': 'Linked List', 'icon': '🔗'},
            {'name': 'Recursion', 'icon': '♻️'},
            {'name': 'Backtracking', 'icon': '↩️'},
        ]
        
        topics = {}
        for topic_data in topics_data:
            topic, created = Topic.objects.get_or_create(
                name=topic_data['name'],
                defaults={'icon': topic_data['icon']}
            )
            topics[topic.name] = topic
        self.stdout.write(self.style.SUCCESS(f'Created {len(topics)} topics'))

        # Create Companies
        self.stdout.write('Creating companies...')
        companies_data = [
            'Google', 'Amazon', 'Microsoft', 'Facebook', 'Apple',
            'Netflix', 'Adobe', 'LinkedIn', 'Uber', 'Tesla'
        ]
        
        companies = {}
        for company_name in companies_data:
            company, created = Company.objects.get_or_create(name=company_name)
            companies[company.name] = company
        self.stdout.write(self.style.SUCCESS(f'Created {len(companies)} companies'))

        # Create Problems
        self.stdout.write('Creating problems...')
        
        problems_data = [
            {
                'problem_number': 1,
                'title': 'Two Sum',
                'difficulty': 'easy',
                'description': '''<p>Given an array of integers <code>nums</code> and an integer <code>target</code>, return indices of the two numbers such that they add up to <code>target</code>.</p>
<p>You may assume that each input would have exactly one solution, and you may not use the same element twice.</p>
<p>You can return the answer in any order.</p>''',
                'constraints': '''<ul>
<li>2 <= nums.length <= 10^4</li>
<li>-10^9 <= nums[i] <= 10^9</li>
<li>-10^9 <= target <= 10^9</li>
<li>Only one valid answer exists.</li>
</ul>''',
                'example_input': '[2,7,11,15]\n9',
                'example_output': '[0,1]',
                'example_explanation': 'Because nums[0] + nums[1] == 9, we return [0, 1].',
                'topics': ['Array', 'Hash Table'],
                'companies': ['Google', 'Amazon', 'Microsoft'],
                'hints': [
                    'Try using a hash map to store numbers you\'ve seen',
                    'For each number, check if target - number exists in the map'
                ],
                'time_complexity': 'O(n)',
                'space_complexity': 'O(n)',
                'test_cases': [
                    {'input': '[2,7,11,15]\n9', 'output': '[0,1]', 'is_sample': True},
                    {'input': '[3,2,4]\n6', 'output': '[1,2]', 'is_sample': True},
                    {'input': '[3,3]\n6', 'output': '[0,1]', 'is_sample': False},
                ]
            },
            {
                'problem_number': 2,
                'title': 'Reverse String',
                'difficulty': 'easy',
                'description': '''<p>Write a function that reverses a string. The input string is given as an array of characters <code>s</code>.</p>
<p>You must do this by modifying the input array in-place with O(1) extra memory.</p>''',
                'constraints': '''<ul>
<li>1 <= s.length <= 10^5</li>
<li>s[i] is a printable ascii character.</li>
</ul>''',
                'example_input': 'hello',
                'example_output': 'olleh',
                'example_explanation': 'The string "hello" becomes "olleh" after reversing.',
                'topics': ['String', 'Array'],
                'companies': ['Apple', 'Microsoft'],
                'hints': [
                    'Use two pointers approach',
                    'Swap characters from start and end moving towards center'
                ],
                'time_complexity': 'O(n)',
                'space_complexity': 'O(1)',
                'test_cases': [
                    {'input': 'hello', 'output': 'olleh', 'is_sample': True},
                    {'input': 'world', 'output': 'dlrow', 'is_sample': True},
                    {'input': 'a', 'output': 'a', 'is_sample': False},
                ]
            },
            {
                'problem_number': 3,
                'title': 'Maximum Subarray',
                'difficulty': 'medium',
                'description': '''<p>Given an integer array <code>nums</code>, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.</p>
<p>A subarray is a contiguous part of an array.</p>''',
                'constraints': '''<ul>
<li>1 <= nums.length <= 10^5</li>
<li>-10^4 <= nums[i] <= 10^4</li>
</ul>''',
                'example_input': '[-2,1,-3,4,-1,2,1,-5,4]',
                'example_output': '6',
                'example_explanation': 'The subarray [4,-1,2,1] has the largest sum 6.',
                'topics': ['Array', 'Dynamic Programming'],
                'companies': ['Google', 'Amazon', 'LinkedIn'],
                'hints': [
                    'Think about Kadane\'s algorithm',
                    'Keep track of current sum and maximum sum seen so far'
                ],
                'time_complexity': 'O(n)',
                'space_complexity': 'O(1)',
                'test_cases': [
                    {'input': '[-2,1,-3,4,-1,2,1,-5,4]', 'output': '6', 'is_sample': True},
                    {'input': '[1]', 'output': '1', 'is_sample': True},
                    {'input': '[5,4,-1,7,8]', 'output': '23', 'is_sample': False},
                ]
            },
            {
                'problem_number': 4,
                'title': 'Valid Parentheses',
                'difficulty': 'easy',
                'description': '''<p>Given a string <code>s</code> containing just the characters <code>'('</code>, <code>')'</code>, <code>'{'</code>, <code>'}'</code>, <code>'['</code> and <code>']'</code>, determine if the input string is valid.</p>
<p>An input string is valid if:</p>
<ol>
<li>Open brackets must be closed by the same type of brackets.</li>
<li>Open brackets must be closed in the correct order.</li>
</ol>''',
                'constraints': '''<ul>
<li>1 <= s.length <= 10^4</li>
<li>s consists of parentheses only '()[]{}'.</li>
</ul>''',
                'example_input': '()[]{}',
                'example_output': 'true',
                'example_explanation': 'All brackets are properly closed.',
                'topics': ['String', 'Stack'],
                'companies': ['Amazon', 'Microsoft', 'Facebook'],
                'hints': [
                    'Use a stack data structure',
                    'When you see an opening bracket, push it to stack',
                    'When you see a closing bracket, check if it matches the top of stack'
                ],
                'time_complexity': 'O(n)',
                'space_complexity': 'O(n)',
                'test_cases': [
                    {'input': '()', 'output': 'true', 'is_sample': True},
                    {'input': '()[]{}', 'output': 'true', 'is_sample': True},
                    {'input': '(]', 'output': 'false', 'is_sample': True},
                    {'input': '{[]}', 'output': 'true', 'is_sample': False},
                ]
            },
            {
                'problem_number': 5,
                'title': 'Merge Two Sorted Lists',
                'difficulty': 'easy',
                'description': '''<p>You are given the heads of two sorted linked lists <code>list1</code> and <code>list2</code>.</p>
<p>Merge the two lists in a one sorted list. The list should be made by splicing together the nodes of the first two lists.</p>
<p>Return the head of the merged linked list.</p>''',
                'constraints': '''<ul>
<li>The number of nodes in both lists is in the range [0, 50].</li>
<li>-100 <= Node.val <= 100</li>
<li>Both list1 and list2 are sorted in non-decreasing order.</li>
</ul>''',
                'example_input': '[1,2,4]\n[1,3,4]',
                'example_output': '[1,1,2,3,4,4]',
                'example_explanation': 'Merging [1,2,4] and [1,3,4] results in [1,1,2,3,4,4]',
                'topics': ['Linked List', 'Recursion'],
                'companies': ['Google', 'Apple'],
                'hints': [
                    'Use a dummy node to simplify edge cases',
                    'Compare values and attach smaller node to result'
                ],
                'time_complexity': 'O(n + m)',
                'space_complexity': 'O(1)',
                'test_cases': [
                    {'input': '[1,2,4]\n[1,3,4]', 'output': '[1,1,2,3,4,4]', 'is_sample': True},
                    {'input': '[]\n[]', 'output': '[]', 'is_sample': True},
                    {'input': '[]\n[0]', 'output': '[0]', 'is_sample': False},
                ]
            },
            {
                'problem_number': 6,
                'title': 'Binary Search',
                'difficulty': 'easy',
                'description': '''<p>Given an array of integers <code>nums</code> which is sorted in ascending order, and an integer <code>target</code>, write a function to search <code>target</code> in <code>nums</code>. If <code>target</code> exists, then return its index. Otherwise, return <code>-1</code>.</p>
<p>You must write an algorithm with <code>O(log n)</code> runtime complexity.</p>''',
                'constraints': '''<ul>
<li>1 <= nums.length <= 10^4</li>
<li>-10^4 < nums[i], target < 10^4</li>
<li>All the integers in nums are unique.</li>
<li>nums is sorted in ascending order.</li>
</ul>''',
                'example_input': '[-1,0,3,5,9,12]\n9',
                'example_output': '4',
                'example_explanation': '9 exists in nums and its index is 4',
                'topics': ['Binary Search', 'Array'],
                'companies': ['Google', 'Amazon'],
                'hints': [
                    'Use binary search template',
                    'Compare middle element with target'
                ],
                'time_complexity': 'O(log n)',
                'space_complexity': 'O(1)',
                'test_cases': [
                    {'input': '[-1,0,3,5,9,12]\n9', 'output': '4', 'is_sample': True},
                    {'input': '[-1,0,3,5,9,12]\n2', 'output': '-1', 'is_sample': True},
                ]
            },
            {
                'problem_number': 7,
                'title': 'Climbing Stairs',
                'difficulty': 'easy',
                'description': '''<p>You are climbing a staircase. It takes <code>n</code> steps to reach the top.</p>
<p>Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?</p>''',
                'constraints': '''<ul>
<li>1 <= n <= 45</li>
</ul>''',
                'example_input': '3',
                'example_output': '3',
                'example_explanation': 'There are three ways to climb to the top: 1+1+1, 1+2, 2+1',
                'topics': ['Dynamic Programming', 'Math'],
                'companies': ['Adobe', 'Amazon'],
                'hints': [
                    'This is similar to Fibonacci sequence',
                    'dp[i] = dp[i-1] + dp[i-2]'
                ],
                'time_complexity': 'O(n)',
                'space_complexity': 'O(1)',
                'test_cases': [
                    {'input': '2', 'output': '2', 'is_sample': True},
                    {'input': '3', 'output': '3', 'is_sample': True},
                    {'input': '5', 'output': '8', 'is_sample': False},
                ]
            },
            {
                'problem_number': 8,
                'title': 'Longest Common Prefix',
                'difficulty': 'easy',
                'description': '''<p>Write a function to find the longest common prefix string amongst an array of strings.</p>
<p>If there is no common prefix, return an empty string <code>""</code>.</p>''',
                'constraints': '''<ul>
<li>1 <= strs.length <= 200</li>
<li>0 <= strs[i].length <= 200</li>
<li>strs[i] consists of only lowercase English letters.</li>
</ul>''',
                'example_input': '["flower","flow","flight"]',
                'example_output': '"fl"',
                'example_explanation': 'The longest common prefix is "fl"',
                'topics': ['String'],
                'companies': ['Google'],
                'hints': [
                    'Compare characters column by column',
                    'Stop when you find a mismatch'
                ],
                'time_complexity': 'O(S)',
                'space_complexity': 'O(1)',
                'test_cases': [
                    {'input': '["flower","flow","flight"]', 'output': '"fl"', 'is_sample': True},
                    {'input': '["dog","racecar","car"]', 'output': '""', 'is_sample': True},
                ]
            },
        ]

        for prob_data in problems_data:
            problem, created = Problem.objects.get_or_create(
                problem_number=prob_data['problem_number'],
                defaults={
                    'title': prob_data['title'],
                    'difficulty': prob_data['difficulty'],
                    'description': prob_data['description'],
                    'constraints': prob_data['constraints'],
                    'example_input': prob_data['example_input'],
                    'example_output': prob_data['example_output'],
                    'example_explanation': prob_data['example_explanation'],
                    'hints': prob_data['hints'],
                    'time_complexity': prob_data['time_complexity'],
                    'space_complexity': prob_data['space_complexity'],
                    'created_by': admin_user,
                    'is_active': True
                }
            )

            if created:
                # Add topics
                for topic_name in prob_data['topics']:
                    if topic_name in topics:
                        problem.topics.add(topics[topic_name])

                # Add companies
                for company_name in prob_data['companies']:
                    if company_name in companies:
                        problem.companies.add(companies[company_name])

                # Add test cases
                for idx, tc in enumerate(prob_data['test_cases']):
                    TestCase.objects.create(
                        problem=problem,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        is_sample=tc['is_sample'],
                        order=idx
                    )

                self.stdout.write(
                    self.style.SUCCESS(f'Created problem: {problem.title}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully populated {Problem.objects.count()} problems!'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                '\nNote: Code templates are auto-generated via signals.'
            )
        )
