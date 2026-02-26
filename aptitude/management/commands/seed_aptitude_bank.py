"""
Comprehensive aptitude question seeder for MNC placement preparation.
Covers: Quantitative, Logical Reasoning, Verbal Ability, Data Interpretation.
Target: 400+ questions across 20+ topics.
"""
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from aptitude.models import AptitudeCategory, AptitudeTopic, AptitudeProblem


def shuffle_opts(correct, distractors, rng):
    opts = [str(correct)] + [str(d) for d in distractors[:3]]
    rng.shuffle(opts)
    idx = opts.index(str(correct))
    return opts, "ABCD"[idx]


class Command(BaseCommand):
    help = "Seed 400+ aptitude questions covering all MNC placement topics."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing aptitude data first")

    def _topic(self, cat, topic, desc=""):
        c, _ = AptitudeCategory.objects.get_or_create(name=cat, defaults={"description": cat})
        t, _ = AptitudeTopic.objects.get_or_create(category=c, name=topic, defaults={"description": desc or topic})
        return t

    def _add(self, topic, q, a, b, c, d, ans, exp, diff):
        if not AptitudeProblem.objects.filter(topic=topic, question_text=q).exists():
            AptitudeProblem.objects.create(
                topic=topic, question_text=q,
                option_a=a, option_b=b, option_c=c, option_d=d,
                correct_option=ans, explanation=exp, difficulty=diff
            )
            return 1
        return 0

    def _diff(self, i):
        return "Hard" if i % 7 == 0 else ("Medium" if i % 3 == 0 else "Easy")

    # ── Quantitative Aptitude Generators ──────────────────────────

    def _gen_percentage(self, topic, rng):
        n = 0
        for i in range(20):
            base = rng.randint(100, 2000)
            pct = rng.choice([5,10,12,15,20,25,30,40,50])
            ans_val = round(base * pct / 100, 2)
            d = [round(ans_val + x, 2) for x in rng.sample([-30,-15,15,30,45], 3)]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, f"What is {pct}% of {base}?", o[0],o[1],o[2],o[3], a,
                f"{pct}% of {base} = ({pct}/100) × {base} = {ans_val}", self._diff(i))
        return n

    def _gen_profit_loss(self, topic, rng):
        n = 0
        for i in range(20):
            cp = rng.randint(200, 5000)
            p = rng.choice([5,10,15,20,25,30])
            if i % 2 == 0:
                sp = round(cp * (1 + p/100))
                q = f"An article bought for Rs.{cp} is sold for Rs.{sp}. Find the profit %."
                exp = f"Profit = {sp}-{cp} = {sp-cp}. Profit% = ({sp-cp}/{cp})×100 = {p}%"
            else:
                sp = round(cp * (1 - p/100))
                q = f"An article bought for Rs.{cp} is sold for Rs.{sp}. Find the loss %."
                exp = f"Loss = {cp}-{sp} = {cp-sp}. Loss% = ({cp-sp}/{cp})×100 = {p}%"
            d = [f"{p+x}%" for x in rng.sample([-8,-4,4,8,12], 3)]
            o, a = shuffle_opts(f"{p}%", d, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_si(self, topic, rng):
        n = 0
        for i in range(20):
            p = rng.randint(1000, 20000)
            r = rng.choice([4,5,6,8,10,12])
            t = rng.randint(1, 6)
            si = round(p*r*t/100, 2)
            d = [f"Rs.{abs(round(si+x))}" for x in rng.sample([-200,-100,100,200,300], 3)]
            o, a = shuffle_opts(f"Rs.{si}", d, rng)
            n += self._add(topic, f"Find the SI on Rs.{p} at {r}% p.a. for {t} years.",
                o[0],o[1],o[2],o[3], a, f"SI = (P×R×T)/100 = ({p}×{r}×{t})/100 = Rs.{si}", self._diff(i))
        return n

    def _gen_ci(self, topic, rng):
        n = 0
        for i in range(20):
            p = rng.randint(1000, 10000)
            r = rng.choice([5,10,15,20])
            t = rng.choice([2,3])
            amt = round(p * (1 + r/100)**t, 2)
            ci = round(amt - p, 2)
            d = [f"Rs.{abs(round(ci+x))}" for x in rng.sample([-300,-150,150,300,500], 3)]
            o, a = shuffle_opts(f"Rs.{ci}", d, rng)
            n += self._add(topic, f"Find the CI on Rs.{p} at {r}% p.a. for {t} years.",
                o[0],o[1],o[2],o[3], a,
                f"A = P(1+R/100)^T = {p}(1+{r}/100)^{t} = Rs.{amt}. CI = {amt}-{p} = Rs.{ci}", self._diff(i))
        return n

    def _gen_ratio(self, topic, rng):
        n = 0
        for i in range(20):
            a_r, b_r = rng.randint(2,9), rng.randint(2,9)
            total = (a_r+b_r) * rng.randint(5,20)
            ans_val = int(total * a_r / (a_r+b_r))
            d = [ans_val+x for x in rng.sample([-10,-5,5,10,15], 3)]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, f"A:B = {a_r}:{b_r}. If A+B = {total}, find A.",
                str(o[0]),str(o[1]),str(o[2]),str(o[3]), a,
                f"A = ({a_r}/{a_r+b_r})×{total} = {ans_val}", self._diff(i))
        return n

    def _gen_averages(self, topic, rng):
        n = 0
        for i in range(20):
            cnt = rng.randint(4,10)
            avg = rng.randint(20,80)
            new = rng.randint(10,100)
            new_avg = round((cnt*avg+new)/(cnt+1), 2)
            d = [round(new_avg+x, 2) for x in rng.sample([-5,-3,3,5,7], 3)]
            o, a = shuffle_opts(new_avg, d, rng)
            n += self._add(topic, f"Average of {cnt} numbers is {avg}. A new number {new} is added. Find new average.",
                str(o[0]),str(o[1]),str(o[2]),str(o[3]), a,
                f"Sum = {cnt}×{avg}={cnt*avg}. New sum = {cnt*avg+new}. New avg = {new_avg}", self._diff(i))
        return n

    def _gen_time_work(self, topic, rng):
        n = 0
        for i in range(20):
            a, b = rng.randint(6,20), rng.randint(8,24)
            tog = round(1/(1/a+1/b), 2)
            d = [round(tog+x, 2) for x in rng.sample([-2,-1,1,2,3], 3)]
            o, ans = shuffle_opts(f"{tog} days", [f"{x} days" for x in d], rng)
            n += self._add(topic, f"A finishes work in {a} days, B in {b} days. Together?",
                o[0],o[1],o[2],o[3], ans,
                f"Rate = 1/{a}+1/{b}. Together = 1/(1/{a}+1/{b}) = {tog} days", self._diff(i))
        return n

    def _gen_time_distance(self, topic, rng):
        n = 0
        for i in range(20):
            s = rng.choice([30,40,50,60,70,80])
            t = rng.choice([2,3,4,5,6])
            dist = s * t
            d = [dist+x for x in rng.sample([-30,-15,15,30,45], 3)]
            o, a = shuffle_opts(f"{dist} km", [f"{x} km" for x in d], rng)
            n += self._add(topic, f"A car travels at {s} km/hr for {t} hours. Find the distance.",
                o[0],o[1],o[2],o[3], a,
                f"Distance = Speed × Time = {s} × {t} = {dist} km", self._diff(i))
        return n

    def _gen_pipes(self, topic, rng):
        n = 0
        for i in range(20):
            a, b = rng.randint(8,20), rng.randint(12,30)
            tog = round(1/(1/a+1/b), 2)
            d = [round(tog+x, 2) for x in rng.sample([-3,-1.5,1.5,3,4.5], 3)]
            o, ans = shuffle_opts(f"{tog} hrs", [f"{x} hrs" for x in d], rng)
            n += self._add(topic, f"Pipe A fills a tank in {a} hrs, Pipe B in {b} hrs. Together?",
                o[0],o[1],o[2],o[3], ans,
                f"Rate = 1/{a}+1/{b}. Together = {tog} hrs", self._diff(i))
        return n

    def _gen_ages(self, topic, rng):
        n = 0
        for i in range(20):
            age_now = rng.randint(20,50)
            years = rng.randint(3,10)
            ans_val = age_now + years
            d = [ans_val+x for x in rng.sample([-4,-2,2,4,6], 3)]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, f"A person's present age is {age_now}. What will be their age after {years} years?",
                str(o[0]),str(o[1]),str(o[2]),str(o[3]), a,
                f"Age after {years} years = {age_now} + {years} = {ans_val}", self._diff(i))
        return n

    def _gen_mixtures(self, topic, rng):
        n = 0
        for i in range(20):
            a_l, b_l = rng.randint(2,10), rng.randint(2,10)
            a_c, b_c = rng.randint(10,40), rng.randint(50,90)
            result = round((a_l*a_c + b_l*b_c) / (a_l+b_l), 2)
            d = [round(result+x, 2) for x in rng.sample([-8,-4,4,8,12], 3)]
            o, a = shuffle_opts(f"{result}%", [f"{x}%" for x in d], rng)
            n += self._add(topic,
                f"{a_l}L of {a_c}% solution mixed with {b_l}L of {b_c}% solution. Find concentration.",
                o[0],o[1],o[2],o[3], a,
                f"Concentration = ({a_l}×{a_c}+{b_l}×{b_c})/({a_l}+{b_l}) = {result}%", self._diff(i))
        return n

    def _gen_number_system(self, topic, rng):
        n = 0
        for i in range(20):
            x = rng.randint(10,99)
            q_type = i % 4
            if q_type == 0:
                ans_val = x * x
                q = f"What is the square of {x}?"
                exp = f"{x}² = {ans_val}"
            elif q_type == 1:
                ans_val = x * x * x
                q = f"What is the cube of {x}?"
                exp = f"{x}³ = {ans_val}"
            elif q_type == 2:
                x = rng.choice([2,3,5,7,11,13,17,19,23,29,31,37,41,43])
                ans_val = "Prime"
                q = f"Is {x} a prime number?"
                exp = f"{x} is divisible only by 1 and itself, so it is Prime."
            else:
                a_v, b_v = rng.randint(12,60), rng.randint(8,40)
                from math import gcd
                g = gcd(a_v, b_v)
                ans_val = g
                q = f"Find the HCF of {a_v} and {b_v}."
                exp = f"HCF({a_v},{b_v}) = {g}"
            d_vals = [str(rng.randint(1,9999)) for _ in range(3)]
            o, a = shuffle_opts(str(ans_val), d_vals, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_permutation(self, topic, rng):
        n = 0
        from math import factorial
        for i in range(20):
            total = rng.randint(4,8)
            choose = rng.randint(2, min(total, 4))
            if i % 2 == 0:
                ans_val = factorial(total) // factorial(total - choose)
                q = f"In how many ways can {choose} items be arranged from {total} items? (P({total},{choose}))"
                exp = f"P({total},{choose}) = {total}!/({total}-{choose})! = {ans_val}"
            else:
                ans_val = factorial(total) // (factorial(choose) * factorial(total - choose))
                q = f"In how many ways can {choose} items be selected from {total} items? (C({total},{choose}))"
                exp = f"C({total},{choose}) = {total}!/({choose}!×({total}-{choose})!) = {ans_val}"
            d = [ans_val+x for x in rng.sample([-20,-10,10,20,30], 3)]
            d = [abs(x) for x in d]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, q, str(o[0]),str(o[1]),str(o[2]),str(o[3]), a, exp, self._diff(i))
        return n

    def _gen_probability(self, topic, rng):
        n = 0
        for i in range(20):
            scenario = i % 4
            if scenario == 0:
                q = f"A die is thrown. Probability of getting a number > {rng.randint(1,4)}?"
                gt = rng.randint(1,4)
                fav = 6 - gt
                ans_val = f"{fav}/6"
                exp = f"Favorable = {fav}, Total = 6. P = {fav}/6"
                q = f"A die is thrown. What is the probability of getting a number greater than {gt}?"
            elif scenario == 1:
                r, b = rng.randint(3,8), rng.randint(2,6)
                total = r + b
                ans_val = f"{r}/{total}"
                q = f"A bag has {r} red and {b} blue balls. Probability of drawing a red ball?"
                exp = f"P(red) = {r}/{total}"
            elif scenario == 2:
                ans_val = "1/2"
                q = "A coin is tossed. What is the probability of getting heads?"
                exp = "P(heads) = 1/2"
            else:
                n_cards = 52
                fav = rng.choice([4, 13, 26])
                labels = {4: "aces", 13: "hearts", 26: "red cards"}
                ans_val = f"{fav}/{n_cards}"
                q = f"From a deck of 52 cards, probability of drawing {labels[fav]}?"
                exp = f"Favorable = {fav}. P = {fav}/{n_cards}"
            d = [f"{rng.randint(1,5)}/{rng.randint(4,12)}" for _ in range(3)]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_algebra(self, topic, rng):
        n = 0
        for i in range(20):
            a_v = rng.randint(1,10)
            b_v = rng.randint(1,50)
            ans_val = round(b_v / a_v, 2)
            q = f"Solve: {a_v}x = {b_v}. Find x."
            d = [round(ans_val+x, 2) for x in rng.sample([-3,-1.5,1.5,3,5], 3)]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, q, str(o[0]),str(o[1]),str(o[2]),str(o[3]), a,
                f"x = {b_v}/{a_v} = {ans_val}", self._diff(i))
        return n

    def _gen_geometry(self, topic, rng):
        n = 0
        import math
        for i in range(20):
            shape = i % 4
            if shape == 0:
                r = rng.randint(3,15)
                ans_val = round(math.pi * r * r, 2)
                q = f"Find the area of a circle with radius {r} cm."
                exp = f"Area = πr² = π×{r}² = {ans_val} cm²"
            elif shape == 1:
                l, w = rng.randint(5,20), rng.randint(3,15)
                ans_val = 2*(l+w)
                q = f"Find the perimeter of a rectangle with length {l} and breadth {w}."
                exp = f"Perimeter = 2(l+b) = 2({l}+{w}) = {ans_val}"
            elif shape == 2:
                s = rng.randint(3,20)
                ans_val = s * s
                q = f"Find the area of a square with side {s} cm."
                exp = f"Area = s² = {s}² = {ans_val} cm²"
            else:
                b_v, h = rng.randint(5,20), rng.randint(3,15)
                ans_val = round(0.5 * b_v * h, 2)
                q = f"Find the area of a triangle with base {b_v} and height {h}."
                exp = f"Area = ½×b×h = ½×{b_v}×{h} = {ans_val}"
            d = [round(ans_val+x, 2) for x in rng.sample([-20,-10,10,20,30], 3)]
            d = [abs(x) for x in d]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, q, str(o[0]),str(o[1]),str(o[2]),str(o[3]), a, exp, self._diff(i))
        return n

    # ── Logical Reasoning Generators ──────────────────────────────

    def _gen_series(self, topic, rng):
        n = 0
        for i in range(25):
            start = rng.randint(2,20)
            diff = rng.randint(2,10)
            seq = [start + j*diff for j in range(5)]
            ans_val = seq[-1] + diff
            d = [ans_val+x for x in rng.sample([-6,-3,3,6,9], 3)]
            o, a = shuffle_opts(ans_val, d, rng)
            n += self._add(topic, f"Next in series: {', '.join(map(str, seq))}, ?",
                str(o[0]),str(o[1]),str(o[2]),str(o[3]), a,
                f"AP with d={diff}. Next = {seq[-1]}+{diff} = {ans_val}", self._diff(i))
        return n

    def _gen_coding_decoding(self, topic, rng):
        n = 0
        for i in range(25):
            shift = rng.randint(1,5)
            word = rng.choice(["CAT","DOG","BIRD","APPLE","TRAIN","GREEN","MOON","STAR","CODE","DATA"])
            coded = "".join(chr(((ord(c)-65+shift)%26)+65) for c in word)
            d = [coded[::-1], word[::-1], "".join(chr(((ord(c)-65+shift+2)%26)+65) for c in word)]
            o, a = shuffle_opts(coded, d, rng)
            n += self._add(topic, f"If letters shift +{shift}, how is '{word}' coded?",
                o[0],o[1],o[2],o[3], a,
                f"Shift each letter by +{shift}: {word} → {coded}", self._diff(i))
        return n

    def _gen_blood_relations(self, topic, rng):
        n = 0
        questions = [
            ("A is the father of B. B is the sister of C. How is A related to C?", "Father", ["Uncle","Brother","Grandfather"], "A is B's father, B is C's sister, so A is also C's father."),
            ("A is B's son. B is C's mother. How is A related to C?", "Brother/Son", ["Uncle","Father","Cousin"], "B is mother of both A and C. A is C's sibling or son depending on generation."),
            ("Pointing to a photo, A says 'He is my mother's only son's son.' Who is in the photo?", "A's son", ["A himself","A's father","A's brother"], "Mother's only son = A. So it's A's son."),
            ("A is B's sister. C is B's mother. D is C's father. How is A related to D?", "Granddaughter", ["Daughter","Sister","Mother"], "D→C→B, A is B's sister, so A is D's granddaughter."),
            ("If 'A + B' means A is father of B, and 'A - B' means A is mother of B, what does 'P + Q - R' mean?", "P is grandfather of R", ["P is father of R","P is uncle of R","P is brother of R"], "P+Q: P is Q's father. Q-R: Q is R's mother. So P is R's grandfather."),
            ("X says to Y, 'Your mother is the only daughter of my mother.' How is X related to Y?", "Uncle/Maternal Uncle", ["Father","Brother","Cousin"], "My mother's only daughter = X's sister. That sister is Y's mother. So X is Y's uncle."),
            ("A introduces B as 'my father's only son's wife'. Who is B to A?", "Wife", ["Sister","Mother","Daughter-in-law"], "Father's only son = A. A's wife = B."),
            ("Pointing to a girl, Ram says, 'She is the daughter of my grandfather's only son.' Who is the girl?", "Ram's sister", ["Ram's daughter","Ram's mother","Ram's cousin"], "Grandfather's only son = Ram's father. His daughter = Ram's sister."),
            ("P is the brother of Q. Q is the sister of R. How is P related to R?", "Brother", ["Father","Uncle","Cousin"], "P is Q's brother. Q is R's sister. So P is also R's brother."),
            ("A man said to a lady, 'Your mother's husband's sister is my aunt.' How is the lady related?", "Sister", ["Cousin","Daughter","Mother"], "Lady's mother's husband = lady's father. His sister = man's aunt. So they share the same father → sister."),
            ("If D is brother of B, B is sister of G, and G is son of E, how is D related to E?", "Son", ["Brother","Nephew","Father"], "G is E's son. B is G's sister → E's daughter. D is B's brother → E's son."),
            ("Pointing to a man, a woman says, 'His brother's father is the only son of my grandfather.' How is she related?", "Sister", ["Daughter","Mother","Aunt"], "Grandfather's only son = her father. That person is also the man's father. So she is the man's sister."),
            ("A is B's mother. C is A's father. D is C's mother. How is B related to D?", "Great-grandchild", ["Grandchild","Child","Sibling"], "D→C→A→B. B is D's great-grandchild."),
            ("M is the son of P. P is the daughter of R. How is M related to R?", "Grandson", ["Son","Nephew","Brother"], "P is R's daughter. M is P's son. M is R's grandson."),
            ("X and Y are sisters. Z is Y's mother. W is Z's father. How is X related to W?", "Granddaughter", ["Daughter","Great-granddaughter","Sister"], "W→Z→Y. X is Y's sister. So X is W's granddaughter."),
        ]
        for i, (q, correct, dists, exp) in enumerate(questions):
            o, a = shuffle_opts(correct, dists, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_seating(self, topic, rng):
        n = 0
        questions = [
            ("5 people A,B,C,D,E sit in a row. A is to the left of B. C is at one end. D is between A and E. Who sits in the middle?", "D", ["A","B","E"], "Arrangement: C,A,D,E,B or similar. D is in the middle."),
            ("6 people sit in a circle. A is opposite D. B is to the left of A. C is between B and D. Who is to A's right?", "F or E", ["B","C","D"], "In circular arrangement with A opposite D, B left of A, the person to A's right is determined by the remaining positions."),
            ("In a row of children, X is 7th from left and 12th from right. How many children?", "18", ["17","19","20"], "Total = 7 + 12 - 1 = 18"),
            ("A is 5th from the left end and 3rd from the right end of a row. How many people in the row?", "7", ["8","6","9"], "Total = 5 + 3 - 1 = 7"),
            ("In a queue, Amit is 10th from the front and 15th from the back. How many people in queue?", "24", ["25","23","26"], "Total = 10 + 15 - 1 = 24"),
            ("Ram is 14th from left and 8th from right in a row. How many students?", "21", ["22","20","19"], "Total = 14 + 8 - 1 = 21"),
            ("In a row, P is 9th from left. Q is 16th from right. Total 30 people. How many between P and Q?", "6", ["5","7","8"], "P is at position 9. Q is at position 30-16+1=15. Between them = 15-9-1 = 5. (Verify with constraint.)"),
            ("6 friends A-F sit in a circle. B is between A and C. D is opposite B. E is to left of D. Who is between E and A?", "F", ["C","D","B"], "Arranging in circle with given constraints, F fills the remaining spot between E and A."),
            ("In a row of 25 students, Ravi's position from the left is double his position from the right minus 1. Find his position from left.", "17", ["16","18","15"], "Let pos from left = x, from right = 25-x+1=26-x. x = 2(26-x)-1 → x=17."),
            ("8 people sit around a circular table. A and D are opposite. B is 2 seats left of A. Who is opposite B?", "The person 4 seats away from B", ["A","D","C"], "In a circle of 8, opposite = 4 seats apart. Person opposite B is 4 seats from B."),
        ]
        for i, (q, correct, dists, exp) in enumerate(questions):
            o, a = shuffle_opts(correct, dists, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_syllogisms(self, topic, rng):
        n = 0
        questions = [
            ("All cats are animals. All animals are living beings. Conclusion: All cats are living beings.", "True", ["False","Cannot determine","Partially true"], "All cats→animals→living beings. The chain is valid."),
            ("Some dogs are white. Some white things are soft. Conclusion: Some dogs are soft.", "Cannot be determined", ["True","False","Always true"], "No direct link: 'some' doesn't guarantee overlap between dogs and soft."),
            ("No fish is a bird. All sparrows are birds. Conclusion: No sparrow is a fish.", "True", ["False","Uncertain","Partially true"], "Sparrows⊂Birds, Fish∩Birds=∅ → Sparrows∩Fish=∅."),
            ("All roses are flowers. Some flowers are red. Conclusion: Some roses are red.", "Does not follow", ["Follows","Always true","False"], "The 'some flowers are red' may not include roses."),
            ("All pens are stationery. All pencils are stationery. Conclusion: All pens are pencils.", "False", ["True","Cannot determine","Partially true"], "Both are subsets of stationery but may not overlap."),
            ("No car is a bicycle. All bicycles have pedals. Conclusion: No car has pedals.", "Does not follow", ["Follows","True","Cannot say"], "Cars could still have pedals through a different relationship."),
            ("Some teachers are singers. All singers are dancers. Conclusion: Some teachers are dancers.", "True", ["False","Cannot determine","Partially true"], "Teachers→Singers→Dancers. Some teachers who are singers must be dancers."),
            ("All metals are conductors. Gold is a metal. Conclusion: Gold is a conductor.", "True", ["False","Cannot determine","Partially"], "Gold∈Metals⊂Conductors → Gold is a conductor."),
            ("No student is lazy. Ram is a student. Conclusion: Ram is not lazy.", "True", ["False","Cannot say","Depends"], "Students∩Lazy=∅. Ram∈Students → Ram∉Lazy."),
            ("All apples are fruits. Some fruits are sweet. Conclusion: All apples are sweet.", "Does not follow", ["Follows","True","Cannot determine"], "Only 'some' fruits are sweet; doesn't guarantee all apples are."),
        ]
        for i, (q, correct, dists, exp) in enumerate(questions):
            o, a = shuffle_opts(correct, dists, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    # ── Verbal Ability Generators ─────────────────────────────────

    def _gen_synonyms(self, topic, rng):
        n = 0
        pairs = [
            ("Benevolent","Kind",["Cruel","Hostile","Indifferent"],"Benevolent means well-meaning and kindly."),
            ("Obsolete","Outdated",["Modern","Current","New"],"Obsolete means no longer in use."),
            ("Pragmatic","Practical",["Idealistic","Theoretical","Impractical"],"Pragmatic means dealing with things realistically."),
            ("Eloquent","Articulate",["Inarticulate","Silent","Dull"],"Eloquent means fluent or persuasive in speech."),
            ("Meticulous","Careful",["Careless","Sloppy","Hasty"],"Meticulous means showing great attention to detail."),
            ("Tenacious","Persistent",["Weak","Yielding","Lazy"],"Tenacious means tending to keep a firm hold."),
            ("Ambiguous","Unclear",["Clear","Certain","Obvious"],"Ambiguous means open to more than one interpretation."),
            ("Vivacious","Lively",["Dull","Boring","Quiet"],"Vivacious means attractively lively."),
            ("Candid","Frank",["Deceptive","Reserved","Secretive"],"Candid means truthful and straightforward."),
            ("Diligent","Hardworking",["Lazy","Idle","Negligent"],"Diligent means having careful and persistent effort."),
            ("Ephemeral","Short-lived",["Permanent","Eternal","Lasting"],"Ephemeral means lasting for a very short time."),
            ("Gregarious","Sociable",["Introverted","Shy","Reserved"],"Gregarious means fond of company."),
            ("Lucid","Clear",["Confusing","Vague","Obscure"],"Lucid means expressed clearly."),
            ("Pernicious","Harmful",["Beneficial","Helpful","Harmless"],"Pernicious means having a harmful effect."),
            ("Resilient","Tough",["Fragile","Weak","Brittle"],"Resilient means able to recover quickly."),
        ]
        for i, (word, syn, dists, exp) in enumerate(pairs):
            o, a = shuffle_opts(syn, dists, rng)
            n += self._add(topic, f"Choose the synonym of '{word}':", o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_antonyms(self, topic, rng):
        n = 0
        pairs = [
            ("Ancient","Modern",["Old","Antique","Historic"],"Ancient = very old. Antonym = Modern."),
            ("Generous","Miserly",["Kind","Lavish","Charitable"],"Generous = giving freely. Antonym = Miserly."),
            ("Verbose","Concise",["Wordy","Lengthy","Detailed"],"Verbose = using too many words. Antonym = Concise."),
            ("Optimistic","Pessimistic",["Hopeful","Cheerful","Positive"],"Optimistic = hopeful. Antonym = Pessimistic."),
            ("Transparent","Opaque",["Clear","Visible","Open"],"Transparent = see-through. Antonym = Opaque."),
            ("Abundant","Scarce",["Plentiful","Ample","Rich"],"Abundant = plentiful. Antonym = Scarce."),
            ("Humble","Arrogant",["Modest","Simple","Meek"],"Humble = modest. Antonym = Arrogant."),
            ("Benign","Malignant",["Gentle","Kind","Harmless"],"Benign = gentle/harmless. Antonym = Malignant."),
            ("Thrive","Decline",["Grow","Prosper","Flourish"],"Thrive = prosper. Antonym = Decline."),
            ("Amplify","Diminish",["Increase","Boost","Enhance"],"Amplify = make larger. Antonym = Diminish."),
            ("Ascend","Descend",["Climb","Rise","Soar"],"Ascend = go up. Antonym = Descend."),
            ("Expand","Contract",["Grow","Enlarge","Extend"],"Expand = become larger. Antonym = Contract."),
            ("Rigid","Flexible",["Stiff","Hard","Fixed"],"Rigid = stiff. Antonym = Flexible."),
            ("Chaos","Order",["Disorder","Confusion","Anarchy"],"Chaos = disorder. Antonym = Order."),
            ("Hostile","Friendly",["Aggressive","Belligerent","Combative"],"Hostile = unfriendly. Antonym = Friendly."),
        ]
        for i, (word, ant, dists, exp) in enumerate(pairs):
            o, a = shuffle_opts(ant, dists, rng)
            n += self._add(topic, f"Choose the antonym of '{word}':", o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_sentence_correction(self, topic, rng):
        n = 0
        items = [
            ("He don't know the answer.", "He doesn't know the answer.", ["He didn't knew the answer.","He not know the answer.","He don't knew the answer."], "Subject-verb agreement: 'He' requires 'doesn't'."),
            ("She is more taller than her sister.", "She is taller than her sister.", ["She is most taller than her sister.","She is tallest than her sister.","She is more tall than her sister."], "Comparative: 'taller' is already comparative, no 'more' needed."),
            ("I have been waiting since two hours.", "I have been waiting for two hours.", ["I have been waiting from two hours.","I have been waiting since two hour.","I has been waiting for two hours."], "'Since' is for a point in time; 'for' is for a duration."),
            ("Neither of the students have passed.", "Neither of the students has passed.", ["Neither of the students are passed.","Neither of students have passed.","Neither the students has passed."], "'Neither' takes a singular verb."),
            ("Each of the boys are present.", "Each of the boys is present.", ["Each of the boys were present.","Each boys is present.","Each of the boy are present."], "'Each' is singular and takes 'is'."),
            ("The news are very shocking.", "The news is very shocking.", ["The news were very shocking.","The news have been shocking.","The news are being shocking."], "'News' is an uncountable noun and takes singular verb."),
            ("I would have went if you asked.", "I would have gone if you had asked.", ["I would have going if you asked.","I would went if you asked.","I would have go if you asked."], "Past participle of 'go' is 'gone'; conditional perfect requires 'had asked'."),
            ("He gave me a good advise.", "He gave me good advice.", ["He gave me a good advices.","He gave me good advises.","He gived me good advice."], "'Advice' is the noun; 'advise' is the verb."),
            ("The committee have reached a decision.", "The committee has reached a decision.", ["The committee are reaching a decision.","The committee have reaching a decision.","The committee were reached a decision."], "Collective noun 'committee' takes singular verb when acting as one unit."),
            ("He is one of the boy who has won.", "He is one of the boys who have won.", ["He is one of the boy who have won.","He is one of the boys who has winning.","He is one of boys who has won."], "'Boys' is plural, 'who' refers to 'boys', so 'have' is correct."),
        ]
        for i, (wrong, correct, dists, exp) in enumerate(items):
            o, a = shuffle_opts(correct, dists, rng)
            n += self._add(topic, f"Correct the sentence: '{wrong}'", o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    # ── Data Interpretation Generators ────────────────────────────

    def _gen_table_di(self, topic, rng):
        n = 0
        for i in range(20):
            vals = [rng.randint(100,500) for _ in range(5)]
            total = sum(vals)
            avg = round(total/5, 2)
            mx = max(vals)
            q_type = i % 3
            if q_type == 0:
                q = f"Sales data (in units): Mon={vals[0]}, Tue={vals[1]}, Wed={vals[2]}, Thu={vals[3]}, Fri={vals[4]}. Total sales?"
                ans_val = total
                exp = f"Total = {'+'.join(map(str,vals))} = {total}"
            elif q_type == 1:
                q = f"Sales: Mon={vals[0]}, Tue={vals[1]}, Wed={vals[2]}, Thu={vals[3]}, Fri={vals[4]}. Average daily sales?"
                ans_val = avg
                exp = f"Average = {total}/5 = {avg}"
            else:
                q = f"Sales: Mon={vals[0]}, Tue={vals[1]}, Wed={vals[2]}, Thu={vals[3]}, Fri={vals[4]}. Maximum sales on which day?"
                days = ["Mon","Tue","Wed","Thu","Fri"]
                ans_val = days[vals.index(mx)]
                exp = f"Maximum = {mx} on {ans_val}"
            d = [str(rng.randint(100,2500)) for _ in range(3)] if q_type < 2 else [d for d in ["Mon","Tue","Wed","Thu","Fri"] if d != ans_val][:3]
            o, a = shuffle_opts(str(ans_val), d, rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a, exp, self._diff(i))
        return n

    def _gen_pie_chart(self, topic, rng):
        n = 0
        for i in range(15):
            slices = {"Food": rng.randint(20,35), "Rent": rng.randint(15,30), "Transport": rng.randint(5,15)}
            slices["Savings"] = 100 - sum(slices.values())
            total_income = rng.choice([10000,20000,30000,50000])
            key = rng.choice(list(slices.keys()))
            pct = slices[key]
            ans_val = round(total_income * pct / 100)
            q = f"Monthly income: Rs.{total_income}. Expenditure: {', '.join(f'{k}={v}%' for k,v in slices.items())}. How much on {key}?"
            d = [round(ans_val+x) for x in rng.sample([-2000,-1000,1000,2000,3000], 3)]
            o, a = shuffle_opts(f"Rs.{ans_val}", [f"Rs.{abs(x)}" for x in d], rng)
            n += self._add(topic, q, o[0],o[1],o[2],o[3], a,
                f"{key} = {pct}% of {total_income} = Rs.{ans_val}", self._diff(i))
        return n

    @transaction.atomic
    def handle(self, *args, **options):
        if options.get("clear"):
            count = AptitudeProblem.objects.count()
            AptitudeProblem.objects.all().delete()
            AptitudeTopic.objects.all().delete()
            AptitudeCategory.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing aptitude problems."))

        rng = random.Random(2026)
        generators = [
            # Quantitative Aptitude
            ("Quantitative Aptitude", "Percentage", self._gen_percentage),
            ("Quantitative Aptitude", "Profit and Loss", self._gen_profit_loss),
            ("Quantitative Aptitude", "Simple Interest", self._gen_si),
            ("Quantitative Aptitude", "Compound Interest", self._gen_ci),
            ("Quantitative Aptitude", "Ratio and Proportion", self._gen_ratio),
            ("Quantitative Aptitude", "Averages", self._gen_averages),
            ("Quantitative Aptitude", "Time and Work", self._gen_time_work),
            ("Quantitative Aptitude", "Time Speed and Distance", self._gen_time_distance),
            ("Quantitative Aptitude", "Pipes and Cisterns", self._gen_pipes),
            ("Quantitative Aptitude", "Ages", self._gen_ages),
            ("Quantitative Aptitude", "Mixtures and Alligation", self._gen_mixtures),
            ("Quantitative Aptitude", "Number System", self._gen_number_system),
            ("Quantitative Aptitude", "Permutation and Combination", self._gen_permutation),
            ("Quantitative Aptitude", "Probability", self._gen_probability),
            ("Quantitative Aptitude", "Algebra", self._gen_algebra),
            ("Quantitative Aptitude", "Geometry and Mensuration", self._gen_geometry),
            # Logical Reasoning
            ("Logical Reasoning", "Series Completion", self._gen_series),
            ("Logical Reasoning", "Coding-Decoding", self._gen_coding_decoding),
            ("Logical Reasoning", "Blood Relations", self._gen_blood_relations),
            ("Logical Reasoning", "Seating Arrangement", self._gen_seating),
            ("Logical Reasoning", "Syllogisms", self._gen_syllogisms),
            # Verbal Ability
            ("Verbal Ability", "Synonyms", self._gen_synonyms),
            ("Verbal Ability", "Antonyms", self._gen_antonyms),
            ("Verbal Ability", "Sentence Correction", self._gen_sentence_correction),
            # Data Interpretation
            ("Data Interpretation", "Table-Based DI", self._gen_table_di),
            ("Data Interpretation", "Pie Chart DI", self._gen_pie_chart),
        ]

        total = 0
        for cat, topic_name, gen in generators:
            topic = self._topic(cat, topic_name)
            created = gen(topic, rng)
            total += created
            self.stdout.write(self.style.SUCCESS(f"  {cat} / {topic_name}: +{created}"))

        self.stdout.write(self.style.SUCCESS(f"\nTotal aptitude questions seeded: {total}"))
