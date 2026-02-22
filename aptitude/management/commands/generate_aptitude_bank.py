import random
from django.core.management.base import BaseCommand
from django.db import transaction

from aptitude.models import AptitudeCategory, AptitudeTopic, AptitudeProblem


def _shuffle_options(correct_value, distractors, rng):
    options = [str(correct_value)] + [str(d) for d in distractors]
    rng.shuffle(options)
    correct_idx = options.index(str(correct_value))
    correct_option = ["A", "B", "C", "D"][correct_idx]
    return options, correct_option


class Command(BaseCommand):
    help = "Generate a large aptitude question bank with options and explanations."

    def add_arguments(self, parser):
        parser.add_argument("--per-topic", type=int, default=30, help="Questions to generate per topic (default: 30)")
        parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")

    def _get_topic(self, category_name, topic_name, description=""):
        category, _ = AptitudeCategory.objects.get_or_create(
            name=category_name,
            defaults={"description": f"{category_name} question bank"},
        )
        topic, _ = AptitudeTopic.objects.get_or_create(
            category=category,
            name=topic_name,
            defaults={"description": description or f"{topic_name} questions"},
        )
        return topic

    def _create_if_missing(self, topic, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, difficulty):
        exists = AptitudeProblem.objects.filter(topic=topic, question_text=question_text).exists()
        if exists:
            return False
        AptitudeProblem.objects.create(
            topic=topic,
            question_text=question_text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_option=correct_option,
            explanation=explanation,
            difficulty=difficulty,
        )
        return True

    def _difficulty(self, i):
        if i % 7 == 0:
            return "Hard"
        if i % 3 == 0:
            return "Medium"
        return "Easy"

    def _generate_percentage(self, topic, n, rng):
        created = 0
        for i in range(n):
            base = rng.randint(80, 1200)
            pct = rng.choice([5, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50])
            correct = round(base * pct / 100, 2)
            distractors = [
                round(base * (pct + rng.choice([-4, -2, 2, 4])) / 100, 2),
                round(base * (pct + rng.choice([-6, 6])) / 100, 2),
                round(base * (pct + rng.choice([-8, 8])) / 100, 2),
            ]
            options, ans = _shuffle_options(correct, distractors[:3], rng)
            q = f"What is {pct}% of {base}?"
            exp = f"{pct}% of {base} = ({pct}/100) x {base} = {correct}."
            if self._create_if_missing(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_profit_loss(self, topic, n, rng):
        created = 0
        for i in range(n):
            cp = rng.randint(200, 3000)
            pct = rng.choice([5, 10, 12, 15, 20, 25, 30])
            is_profit = rng.choice([True, False])
            if is_profit:
                sp = round(cp * (1 + pct / 100), 2)
                q = f"A shopkeeper buys an item for Rs. {cp} and sells it for Rs. {sp}. What is the profit percentage?"
                correct = pct
                exp = f"Profit = {sp} - {cp}. Profit % = (Profit/CP) x 100 = {pct}%."
            else:
                sp = round(cp * (1 - pct / 100), 2)
                q = f"A shopkeeper buys an item for Rs. {cp} and sells it for Rs. {sp}. What is the loss percentage?"
                correct = pct
                exp = f"Loss = {cp} - {sp}. Loss % = (Loss/CP) x 100 = {pct}%."
            distractors = [max(1, correct + d) for d in rng.sample([-8, -5, -3, 3, 5, 8], 3)]
            options, ans = _shuffle_options(f"{correct}%", [f"{d}%" for d in distractors], rng)
            if self._create_if_missing(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_simple_interest(self, topic, n, rng):
        created = 0
        for i in range(n):
            p = rng.randint(1000, 20000)
            r = rng.choice([4, 5, 6, 8, 10, 12, 15])
            t = rng.randint(1, 8)
            si = round((p * r * t) / 100, 2)
            q = f"What is the simple interest on Rs. {p} at {r}% per annum for {t} years?"
            distractors = [round(si + d, 2) for d in rng.sample([-300, -200, -100, 100, 200, 300], 3)]
            options, ans = _shuffle_options(f"Rs. {si}", [f"Rs. {abs(d)}" for d in distractors], rng)
            exp = f"SI = (P x R x T)/100 = ({p} x {r} x {t})/100 = Rs. {si}."
            if self._create_if_missing(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_ratio(self, topic, n, rng):
        created = 0
        for i in range(n):
            a = rng.randint(2, 12)
            b = rng.randint(2, 12)
            total = (a + b) * rng.randint(8, 30)
            correct = int(total * a / (a + b))
            q = f"The ratio of A:B is {a}:{b}. If A+B = {total}, find A."
            distractors = [correct + d for d in rng.sample([-12, -8, 8, 12, 16], 3)]
            options, ans = _shuffle_options(correct, distractors, rng)
            exp = f"A = ({a}/{a+b}) x {total} = {correct}."
            if self._create_if_missing(topic, q, str(options[0]), str(options[1]), str(options[2]), str(options[3]), ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_averages(self, topic, n, rng):
        created = 0
        for i in range(n):
            count = rng.randint(4, 9)
            avg = rng.randint(20, 80)
            total = count * avg
            new_num = rng.randint(10, 100)
            new_avg = round((total + new_num) / (count + 1), 2)
            q = f"The average of {count} numbers is {avg}. If one more number {new_num} is included, what is the new average?"
            distractors = [round(new_avg + d, 2) for d in rng.sample([-5, -3, 3, 5, 7], 3)]
            options, ans = _shuffle_options(new_avg, distractors, rng)
            exp = f"Old sum = {count} x {avg} = {total}. New sum = {total}+{new_num}. New average = {new_avg}."
            if self._create_if_missing(topic, q, str(options[0]), str(options[1]), str(options[2]), str(options[3]), ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_time_work(self, topic, n, rng):
        created = 0
        for i in range(n):
            a = rng.randint(6, 20)
            b = rng.randint(8, 24)
            together = round(1 / (1 / a + 1 / b), 2)
            q = f"A can finish a work in {a} days and B can finish it in {b} days. In how many days can they finish it together?"
            distractors = [round(together + d, 2) for d in rng.sample([-2.0, -1.0, 1.0, 2.0, 3.0], 3)]
            options, ans = _shuffle_options(together, distractors, rng)
            exp = f"Combined rate = 1/{a} + 1/{b}. Days = 1 / combined rate = {together}."
            if self._create_if_missing(topic, q, f"{options[0]} days", f"{options[1]} days", f"{options[2]} days", f"{options[3]} days", ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_series(self, topic, n, rng):
        created = 0
        for i in range(n):
            start = rng.randint(2, 20)
            diff = rng.randint(2, 10)
            seq = [start + j * diff for j in range(5)]
            correct = seq[-1] + diff
            q = f"Find the next number in the series: {', '.join(map(str, seq))}, ?"
            distractors = [correct + d for d in rng.sample([-6, -3, 3, 6, 9], 3)]
            options, ans = _shuffle_options(correct, distractors, rng)
            exp = f"This is an arithmetic progression with common difference {diff}. Next term is {correct}."
            if self._create_if_missing(topic, q, str(options[0]), str(options[1]), str(options[2]), str(options[3]), ans, exp, self._difficulty(i)):
                created += 1
        return created

    def _generate_coding_decoding(self, topic, n, rng):
        created = 0
        for i in range(n):
            shift = rng.randint(1, 5)
            word = rng.choice(["CAT", "DOG", "BIRD", "APPLE", "TRAIN", "GREEN"])

            def encode(w):
                out = []
                for ch in w:
                    if "A" <= ch <= "Z":
                        out.append(chr(((ord(ch) - 65 + shift) % 26) + 65))
                    else:
                        out.append(ch)
                return "".join(out)

            coded = encode(word)
            q = f"If each letter is shifted by +{shift} positions, how is '{word}' coded?"
            correct = coded
            distractors = [encode(word[::-1]), encode(word[:-1] + word[-1]), word, encode(word.lower().upper())[::-1]]
            options, ans = _shuffle_options(correct, distractors[:3], rng)
            exp = f"Apply Caesar shift +{shift} to each letter: {word} -> {correct}."
            if self._create_if_missing(topic, q, options[0], options[1], options[2], options[3], ans, exp, self._difficulty(i)):
                created += 1
        return created

    @transaction.atomic
    def handle(self, *args, **options):
        per_topic = max(1, options["per_topic"])
        rng = random.Random(options["seed"])

        generators = [
            ("Quantitative Aptitude", "Percentage", self._generate_percentage),
            ("Quantitative Aptitude", "Profit and Loss", self._generate_profit_loss),
            ("Quantitative Aptitude", "Simple Interest", self._generate_simple_interest),
            ("Quantitative Aptitude", "Ratio and Proportion", self._generate_ratio),
            ("Quantitative Aptitude", "Averages", self._generate_averages),
            ("Quantitative Aptitude", "Time and Work", self._generate_time_work),
            ("Logical Reasoning", "Series Completion", self._generate_series),
            ("Logical Reasoning", "Coding-Decoding", self._generate_coding_decoding),
        ]

        total_created = 0
        for category_name, topic_name, generator in generators:
            topic = self._get_topic(category_name, topic_name)
            created = generator(topic, per_topic, rng)
            total_created += created
            self.stdout.write(self.style.SUCCESS(f"{category_name} / {topic_name}: +{created} questions"))

        self.stdout.write(self.style.SUCCESS(f"\nGenerated total {total_created} aptitude questions."))
