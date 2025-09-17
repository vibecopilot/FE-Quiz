# exams/management/commands/import_questions_xlsx.py
import re
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

try:
    import pandas as pd
except Exception as e:
    raise CommandError("pandas is required: pip install pandas openpyxl") from e

from exams.models import Question, QuestionOption


QUESTION_RE = re.compile(r"^\s*question\b\s*[:\-]?\s*(.*)$", re.IGNORECASE)
OPTION_RE   = re.compile(r"^\s*\(?([A-Ea-e])\)?[.)]?\s*(.*)$")
ANSWER_RE   = re.compile(r"^\s*answer\b\s*[:\-]?\s*\(?([A-Ea-e])\)?", re.IGNORECASE)
EXPL_RE     = re.compile(r"^\s*explanation\b\s*[:\-]?\s*(.*)$", re.IGNORECASE)

def _clean(s):
    if s is None:
        return ""
    s = str(s).strip()
    # strip stray "Q1." / "1)" numbers at start
    s = re.sub(r"^\s*(?:Q?\d+[.)-]\s*)", "", s, flags=re.IGNORECASE)
    return s

def parse_lines(lines):
    """
    lines: list[str] from the single first column of the sheet
    Returns: list of dicts: {text, options: [(letter,text),...], correct:'a'..'e', explanation}
    """
    out = []
    i = 0
    n = len(lines)

    while i < n:
        row = _clean(lines[i])
        m_q = QUESTION_RE.match(row)
        if not m_q:
            i += 1
            continue

        q_text = m_q.group(1).strip() or row  # text after 'Question:'
        i += 1
        options = []
        explanation = ""
        correct = None

        while i < n:
            curr = _clean(lines[i])
            if not curr:
                i += 1
                continue

            # end of this block: found Answer line
            m_ans = ANSWER_RE.match(curr)
            if m_ans:
                correct = m_ans.group(1).lower()
                i += 1
                # Optional single-line explanation right after Answer:
                if i < n:
                    m_ex = EXPL_RE.match(_clean(lines[i]))
                    if m_ex:
                        explanation = m_ex.group(1).strip()
                        i += 1
                break

            # collect options (a)-(e)
            m_opt = OPTION_RE.match(curr)
            if m_opt:
                letter = m_opt.group(1).lower()
                text = m_opt.group(2).strip()
                # multi-line option continuation support
                i += 1
                while i < n and (not QUESTION_RE.match(_clean(lines[i])) 
                                 and not ANSWER_RE.match(_clean(lines[i]))
                                 and not OPTION_RE.match(_clean(lines[i]))):
                    cont = _clean(lines[i])
                    if cont:
                        text = (text + " " + cont).strip()
                    i += 1
                options.append((letter, text))
                continue

            # extra line(s) belonging to the question stem
            q_text = (q_text + " " + curr).strip()
            i += 1

        if not options or not correct:
            # skip malformed blocks
            continue

        out.append({
            "text": q_text,
            "options": options,
            "correct": correct,
            "explanation": explanation,
        })

    return out


class Command(BaseCommand):
    help = "Import single-choice questions from an Excel file laid out as 'Question/Options/Answer' rows."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to .xlsx file")
        parser.add_argument("--sheet", default="Sheet1", help="Worksheet name (default: Sheet1)")
        parser.add_argument("--reset", action="store_true", help="Delete ALL existing questions before import")
        parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to DB")
        parser.add_argument("--time-limit", type=int, default=120, help="time_limit_seconds per question")
        parser.add_argument("--marks", type=float, default=1.0)
        parser.add_argument("--neg-marks", type=float, default=0.0)

    def handle(self, *args, **opts):
        path = opts["file"]
        sheet = opts["sheet"]
        self.stdout.write(f"Reading file: {path}")
        self.stdout.write(f"Using sheet: {sheet}")

        try:
            # IMPORTANT: header=None so first row is NOT swallowed as header
            df = pd.read_excel(path, sheet_name=sheet, header=None, engine="openpyxl")
        except Exception as e:
            raise CommandError(f"Failed to read Excel: {e}")

        col0 = df.iloc[:, 0].tolist()
        # drop NaNs and empty lines
        lines = [str(x) for x in col0 if str(x).strip() and str(x).strip().lower() != "nan"]

        blocks = parse_lines(lines)
        self.stdout.write(f"Parsed {len(blocks)} question(s) from Excel.")

        if opts["dry_run"]:
            self.stdout.write("Dry-run complete. No DB changes made.")
            return

        with transaction.atomic():
            if opts["reset"]:
                self.stdout.write("Purging existing questions (cascade deletes options)...")
                Question.objects.all().delete()

            created_q = 0
            created_o = 0

            for b in blocks:
                q = Question.objects.create(
                    text=b["text"],
                    explanation=b.get("explanation", ""),
                    question_type="SINGLE_CHOICE",
                    time_limit_seconds=opts["time_limit"],
                    marks=Decimal(str(opts["marks"])),
                    negative_marks=Decimal(str(opts["neg_marks"])),
                    is_active=True,
                )
                created_q += 1

                # order options as A..E, regardless of which letters were present
                letters = ["a", "b", "c", "d", "e"]
                letter_to_text = {l: t for l, t in b["options"]}
                for order, l in enumerate(letters, start=1):
                    if l in letter_to_text:
                        QuestionOption.objects.create(
                            question=q,
                            text=letter_to_text[l],
                            is_correct=(l == b["correct"]),
                            order=order,
                        )
                        created_o += 1

        self.stdout.write(f"Import complete. Created {created_q} question(s) and {created_o} option(s).")
