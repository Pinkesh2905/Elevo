import random
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from aptitude.models import AptitudeCategory, AptitudeProblem, AptitudeTopic


def _shuffle(correct, distractors, rng):
    options = [correct] + distractors[:3]
    rng.shuffle(options)
    answer = ["A", "B", "C", "D"][options.index(correct)]
    return options, answer


class Command(BaseCommand):
    help = "Expand aptitude bank to cover placement-test topics across all major categories."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=2026, help="Random seed")
        parser.add_argument("--per-topic", type=int, default=10, help="Target questions per generated topic")

    def _topic(self, category_name, topic_name, description=""):
        category, _ = AptitudeCategory.objects.get_or_create(
            name=category_name,
            defaults={"description": f"{category_name} for placement preparation"},
        )
        topic, _ = AptitudeTopic.objects.get_or_create(
            category=category,
            name=topic_name,
            defaults={"description": description or f"{topic_name} questions"},
        )
        return topic

    def _create(self, topic, q, a, b, c, d, correct, explanation, difficulty):
        if AptitudeProblem.objects.filter(topic=topic, question_text=q).exists():
            return False
        AptitudeProblem.objects.create(
            topic=topic,
            question_text=q,
            option_a=a,
            option_b=b,
            option_c=c,
            option_d=d,
            correct_option=correct,
            explanation=explanation,
            difficulty=difficulty,
        )
        return True

    def _difficulty(self, i):
        if i % 6 == 0:
            return "Hard"
        if i % 2 == 0:
            return "Medium"
        return "Easy"

    def _gen_time_speed_distance(self, topic, n, rng):
        made = 0
        for i in range(n):
            dist = rng.randint(60, 240)
            speed = rng.randint(20, 80)
            time = round(dist / speed, 2)
            q = f"A vehicle covers {dist} km at {speed} km/h. How much time does it take?"
            wrong = [round(time + x, 2) for x in rng.sample([-1.5, -0.5, 0.5, 1.5, 2.0], 3)]
            options, ans = _shuffle(f"{time} hours", [f"{w} hours" for w in wrong], rng)
            exp = f"Time = Distance / Speed = {dist}/{speed} = {time} hours."
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_probability(self, topic, n, rng):
        made = 0
        for i in range(n):
            total = rng.randint(6, 20)
            fav = rng.randint(1, total - 1)
            q = f"A random outcome is selected from {total} equally likely outcomes. {fav} outcomes are favorable. What is the probability of a favorable outcome?"
            correct = f"{fav}/{total}"
            wrong = [f"{fav+1}/{total}", f"{fav}/{max(1,total-1)}", f"{max(1,fav-1)}/{total}"]
            options, ans = _shuffle(correct, wrong, rng)
            exp = f"Probability = favorable / total = {fav}/{total}."
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_permutation_combination(self, topic, n, rng):
        made = 0
        for i in range(n):
            n_val = rng.randint(5, 10)
            r_val = rng.randint(2, min(4, n_val - 1))
            if rng.choice([True, False]):
                correct_num = 1
                for x in range(n_val, n_val - r_val, -1):
                    correct_num *= x
                q = f"How many permutations can be formed by arranging {r_val} objects selected from {n_val} distinct objects?"
                exp = f"nPr = n!/(n-r)! = {correct_num}."
            else:
                num = 1
                den = 1
                for x in range(n_val, n_val - r_val, -1):
                    num *= x
                for x in range(2, r_val + 1):
                    den *= x
                correct_num = num // den
                q = f"How many combinations can be formed by selecting {r_val} objects from {n_val} distinct objects?"
                exp = f"nCr = n!/(r!(n-r)!) = {correct_num}."
            wrong = [max(1, correct_num + d) for d in rng.sample([-12, -6, 6, 12, 18], 3)]
            options, ans = _shuffle(str(correct_num), [str(w) for w in wrong], rng)
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_number_system(self, topic, n, rng):
        made = 0
        for i in range(n):
            a = rng.randint(20, 180)
            b = rng.randint(20, 180)
            q = f"What is the HCF (GCD) of {a} and {b}?"
            x, y = a, b
            while y:
                x, y = y, x % y
            correct = x
            wrong = [max(1, correct + d) for d in rng.sample([-8, -4, 4, 8, 12], 3)]
            options, ans = _shuffle(str(correct), [str(w) for w in wrong], rng)
            exp = f"Using Euclidean algorithm, gcd({a}, {b}) = {correct}."
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_algebra(self, topic, n, rng):
        made = 0
        for i in range(n):
            a = rng.randint(2, 12)
            b = rng.randint(2, 12)
            x = rng.randint(2, 20)
            c = a * x + b
            q = f"Solve for x: {a}x + {b} = {c}"
            correct = str(x)
            wrong = [str(max(1, x + d)) for d in rng.sample([-4, -2, 2, 4, 6], 3)]
            options, ans = _shuffle(correct, wrong, rng)
            exp = f"{a}x = {c}-{b} => x = {(c-b)}/{a} = {x}."
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_direction_sense(self, topic, n, rng):
        made = 0
        cases = [
            ("A person walks 10 m North, then 10 m East. In which direction is he from the start?", "North-East", ["North-West", "South-East", "West"], "Moving north then east places the person in North-East direction."),
            ("A person walks 8 m South, then 8 m West. In which direction is he from the start?", "South-West", ["South-East", "North-West", "East"], "Moving south then west places the person in South-West direction."),
            ("A person faces North and turns right. Which direction is he facing now?", "East", ["West", "South", "North"], "Right turn from North is East."),
            ("A person faces West and turns left. Which direction is he facing now?", "South", ["North", "East", "West"], "Left turn from West is South."),
        ]
        for i in range(n):
            q, correct, wrong, exp = cases[i % len(cases)]
            options, ans = _shuffle(correct, wrong, rng)
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_syllogism(self, topic, n, rng):
        made = 0
        cases = [
            ("Statements: All cats are animals. All animals are living beings. Conclusion: All cats are living beings.", "Follows", ["Does not follow", "Only first statement follows", "Cannot be determined"], "By transitivity, cats are animals and animals are living beings."),
            ("Statements: Some students are athletes. All athletes are disciplined. Conclusion: Some students are disciplined.", "Follows", ["Does not follow", "Only some are not disciplined", "Cannot be determined"], "If some students are athletes and all athletes are disciplined, those students are disciplined."),
            ("Statements: All A are B. All B are C. Conclusion: All C are A.", "Does not follow", ["Follows", "Only if A is empty", "Cannot be determined"], "The reverse relation is not implied."),
        ]
        for i in range(n):
            q, correct, wrong, exp = cases[i % len(cases)]
            options, ans = _shuffle(correct, wrong, rng)
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_verbal(self, topic, n, rng, mode):
        made = 0
        banks = {
            "Synonyms": [
                ("Choose the synonym of 'Rapid'.", "Fast", ["Slow", "Weak", "Late"], "Rapid means fast."),
                ("Choose the synonym of 'Abundant'.", "Plentiful", ["Scarce", "Tiny", "Rare"], "Abundant means plentiful."),
                ("Choose the synonym of 'Brief'.", "Short", ["Long", "Dense", "Opaque"], "Brief means short."),
            ],
            "Antonyms": [
                ("Choose the antonym of 'Expand'.", "Contract", ["Increase", "Enlarge", "Grow"], "Contract is opposite of expand."),
                ("Choose the antonym of 'Ancient'.", "Modern", ["Old", "Historic", "Primitive"], "Modern is opposite of ancient."),
                ("Choose the antonym of 'Optimistic'.", "Pessimistic", ["Hopeful", "Cheerful", "Positive"], "Pessimistic is opposite of optimistic."),
            ],
            "Error Spotting": [
                ("Identify the incorrect segment: 'She do not / like coffee / in the morning / No error'.", "She do not", ["like coffee", "in the morning", "No error"], "Subject-verb agreement: should be 'She does not'."),
                ("Identify the incorrect segment: 'Each of the boys / were present / in class / No error'.", "were present", ["Each of the boys", "in class", "No error"], "After 'Each', singular verb should be used: 'was present'."),
            ],
            "Sentence Improvement": [
                ("Choose the best improvement: 'He is senior than me.'", "He is senior to me.", ["He is senior from me.", "He is senior over me.", "No improvement"], "Use 'senior to', not 'senior than'."),
                ("Choose the best improvement: 'I prefer tea than coffee.'", "I prefer tea to coffee.", ["I prefer tea over coffee than.", "I prefer tea over to coffee.", "No improvement"], "Use 'prefer X to Y'."),
            ],
            "Para Jumbles": [
                ("Select the correct opening sentence for a paragraph about time management: (A) Therefore, deadlines are met. (B) Planning each day improves productivity. (C) Finally, stress decreases. (D) As a result, priorities stay clear.", "B", ["A", "C", "D"], "A paragraph should start with a general point before results."),
            ],
        }
        cases = banks.get(mode, [])
        if not cases:
            return 0
        for i in range(n):
            q, correct, wrong, exp = cases[i % len(cases)]
            options, ans = _shuffle(correct, wrong, rng)
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_technical(self, topic, n, rng, mode):
        made = 0
        banks = {
            "DBMS": [
                ("Which normal form removes transitive dependency?", "Third Normal Form (3NF)", ["First Normal Form (1NF)", "Second Normal Form (2NF)", "Boyce-Codd Normal Form"], "3NF removes transitive dependency."),
                ("Which SQL command removes all rows but keeps table structure?", "TRUNCATE", ["DELETE", "DROP", "REMOVE"], "TRUNCATE clears rows and keeps table structure."),
                ("What is a primary key?", "A unique identifier for each row", ["A column with duplicates", "A foreign table reference only", "An optional text field"], "Primary key uniquely identifies each record."),
            ],
            "Operating Systems": [
                ("Which scheduling algorithm can cause starvation?", "Priority Scheduling", ["FCFS", "Round Robin", "SJF with aging"], "Priority scheduling may starve low-priority processes."),
                ("What does paging help avoid?", "External fragmentation", ["Deadlock", "Race condition", "Starvation"], "Paging eliminates external fragmentation."),
                ("A process currently in CPU is in which state?", "Running", ["Ready", "Waiting", "Terminated"], "The executing process is in Running state."),
            ],
            "Computer Networks": [
                ("Which protocol is connection-oriented?", "TCP", ["UDP", "ICMP", "ARP"], "TCP establishes a connection before transfer."),
                ("Which layer handles routing?", "Network Layer", ["Transport Layer", "Session Layer", "Data Link Layer"], "Routing is a Network layer function."),
                ("Default HTTPS port is:", "443", ["80", "21", "25"], "HTTPS runs on port 443."),
            ],
            "OOPs": [
                ("Which OOP concept allows one interface, many forms?", "Polymorphism", ["Encapsulation", "Abstraction", "Inheritance"], "Polymorphism supports multiple forms."),
                ("Binding data and methods together is:", "Encapsulation", ["Polymorphism", "Inheritance", "Overloading"], "Encapsulation wraps data and behavior."),
                ("Creating a new class from an existing class is:", "Inheritance", ["Encapsulation", "Abstraction", "Instantiation"], "Inheritance extends existing class behavior."),
            ],
            "Data Structures": [
                ("Average search complexity in a balanced BST is:", "O(log n)", ["O(n)", "O(1)", "O(n log n)"], "Balanced BST search is logarithmic."),
                ("Which data structure is used for BFS?", "Queue", ["Stack", "Heap", "Hash Table"], "BFS explores level-wise using queue."),
                ("Which data structure supports LIFO?", "Stack", ["Queue", "Deque (FIFO mode)", "Linked Hash Map"], "LIFO access is stack."),
            ],
            "Complexity Analysis": [
                ("What is the time complexity of binary search?", "O(log n)", ["O(n)", "O(1)", "O(n log n)"], "Binary search halves search space each step."),
                ("Nested loops each running n times usually yield:", "O(n^2)", ["O(n)", "O(log n)", "O(n log n)"], "Two full loops over n give n^2 operations."),
                ("Merge sort worst-case complexity is:", "O(n log n)", ["O(n^2)", "O(log n)", "O(n)"], "Merge sort divide+merge gives n log n."),
            ],
            "SQL": [
                ("Which clause filters grouped results?", "HAVING", ["WHERE", "ORDER BY", "SELECT"], "HAVING filters after GROUP BY."),
                ("Which join returns only matching rows from both tables?", "INNER JOIN", ["LEFT JOIN", "RIGHT JOIN", "FULL JOIN"], "INNER JOIN returns intersections."),
                ("Which SQL function returns number of rows?", "COUNT()", ["SUM()", "AVG()", "LEN()"], "COUNT() counts rows or non-null values."),
            ],
        }
        cases = banks.get(mode, [])
        if not cases:
            return 0
        for i in range(n):
            q, correct, wrong, exp = cases[i % len(cases)]
            options, ans = _shuffle(correct, wrong, rng)
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    def _gen_di(self, topic, n, rng, mode):
        made = 0
        for i in range(n):
            a = rng.randint(40, 180)
            b = rng.randint(40, 180)
            if mode == "Tables":
                q = f"In a table, Sales in Q1 = {a} and Q2 = {b}. What is the percentage increase from Q1 to Q2?"
                correct = round(((b - a) / a) * 100, 2)
                exp = f"Percentage change = (({b}-{a})/{a}) x 100 = {correct}%."
            elif mode == "Bar Graph":
                q = f"A bar graph shows values {a} and {b} for two products. What is their absolute difference?"
                correct = abs(b - a)
                exp = f"Difference = |{b}-{a}| = {correct}."
            elif mode == "Pie Chart":
                total = a + b + rng.randint(40, 160)
                correct = round(a * 360 / total, 2)
                q = f"In a pie chart, category A value is {a} out of total {total}. What central angle represents category A?"
                exp = f"Angle = ({a}/{total}) x 360 = {correct} degrees."
            elif mode == "Line Graph":
                q = f"A line graph shows metric rising from {a} to {b}. What is the net change?"
                correct = b - a
                exp = f"Net change = {b}-{a} = {correct}."
            else:
                q = f"A caselet has two sections with {a} and {b} applicants. What is total applicants?"
                correct = a + b
                exp = f"Total = {a}+{b} = {correct}."

            wrong = [correct + d for d in rng.sample([-15, -8, 8, 15, 20], 3)]
            options, ans = _shuffle(str(correct), [str(w) for w in wrong], rng)
            if self._create(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                made += 1
        return made

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        per_topic = max(3, options["per_topic"])

        created = defaultdict(int)

        # Quantitative
        created["Time Speed and Distance"] += self._gen_time_speed_distance(
            self._topic("Quantitative Aptitude", "Time Speed and Distance"), per_topic, rng
        )
        created["Probability"] += self._gen_probability(
            self._topic("Quantitative Aptitude", "Probability"), per_topic, rng
        )
        created["Permutation and Combination"] += self._gen_permutation_combination(
            self._topic("Quantitative Aptitude", "Permutation and Combination"), per_topic, rng
        )
        created["Number System"] += self._gen_number_system(
            self._topic("Quantitative Aptitude", "Number System"), per_topic, rng
        )
        created["Algebra"] += self._gen_algebra(
            self._topic("Quantitative Aptitude", "Algebra"), per_topic, rng
        )

        # Logical reasoning
        created["Direction Sense"] += self._gen_direction_sense(
            self._topic("Logical Reasoning", "Direction Sense"), per_topic, rng
        )
        created["Syllogism"] += self._gen_syllogism(
            self._topic("Logical Reasoning", "Syllogism"), per_topic, rng
        )

        # Verbal
        for topic_name in ["Synonyms", "Antonyms", "Error Spotting", "Sentence Improvement", "Para Jumbles"]:
            created[topic_name] += self._gen_verbal(
                self._topic("Verbal Ability", topic_name),
                per_topic,
                rng,
                topic_name,
            )

        # Data interpretation
        for topic_name in ["Tables", "Bar Graph", "Pie Chart", "Line Graph", "Caselet DI"]:
            created[topic_name] += self._gen_di(
                self._topic("Data Interpretation", topic_name),
                per_topic,
                rng,
                topic_name,
            )

        # Technical aptitude
        for topic_name in ["DBMS", "Operating Systems", "Computer Networks", "OOPs", "Data Structures", "Complexity Analysis", "SQL"]:
            created[topic_name] += self._gen_technical(
                self._topic("Technical Aptitude", topic_name),
                per_topic,
                rng,
                topic_name,
            )

        total_created = sum(created.values())
        for topic_name in sorted(created.keys()):
            self.stdout.write(self.style.SUCCESS(f"{topic_name}: +{created[topic_name]}"))
        self.stdout.write(self.style.SUCCESS(f"\nExpanded bank by {total_created} questions."))
