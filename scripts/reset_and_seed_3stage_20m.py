# scripts/reset_and_seed_3stage_20m_300q.py
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from common.enums import Difficulty
from exams.models import (
    Question, QuestionOption,
    Quiz, QuizStage, StageRandomRule,
    StageQuestion,
    QuizAttempt, QuizStageAttempt, AttemptAnswer, StageAttemptItem,
    LeaderboardEntry, StageAdmission, AccessToken,
)

# -------------------
# Helpers to build MCQs
# -------------------
def _mk_q(topic, diff, text, options, correct_index):
    q = Question.objects.create(
        text=text.strip(),
        explanation="",
        question_type="single",  # single-choice
        subspecialty=topic.lower(),
        difficulty=diff,
        region_hint="",
        marks=1,
        negative_marks=0.25,
        time_limit_seconds=60,
        is_active=True,
        tags={"topic": topic.lower()},
    )
    bulk = []
    for i, opt in enumerate(options, start=1):
        bulk.append(QuestionOption(
            question=q, text=opt, is_correct=(i-1) == int(correct_index), order=i
        ))
    QuestionOption.objects.bulk_create(bulk)
    return q

def _gen_items(templates, count_needed):
    """
    templates: list of callables f(i)->(text, options, correct_index)
    Will cycle templates with index i to reach count_needed.
    """
    items = []
    for i in range(count_needed):
        t = templates[i % len(templates)]
        items.append(t(i))
    return items

# ---------- TEMPLATES PER TOPIC ----------
def _py_templates():
    # Easy
    e = [
        lambda i: (f"Python {3 + (i % 3) + 8}.x: which keyword defines a function?",
                   ["def", "function", "lambda", "fn"], 0),
        lambda i: (f"In Python, which type is immutable (variant {i})?",
                   ["tuple", "list", "set", "dict"], 0),
        lambda i: (f"Which method appends an item to list L (case {i})?",
                   ["append()", "add()", "push()", "insert(0, x)"], 0),
        lambda i: (f"Create a virtual env for project{i}:",
                   ["python -m venv .venv", "pip install venv", "virtualenv is stdlib", "pipenv shell"], 0),
        lambda i: (f"What does len(range({i%7+3})) return?",
                   [str(i%7+3), str(i%7+2), str(i%7+4), "TypeError"], 0),
        lambda i: (f"Which operator concatenates two lists (trial {i})?",
                   ["+", "&", "%", "//"], 0),
    ]
    # Medium
    m = [
        lambda i: (f"What does 'yield' create in generator g{i}()?",
                   ["a generator", "a context manager", "a coroutine only", "a list"], 0),
        lambda i: (f"Which is TRUE about tuple vs list (set {i})?",
                   ["tuple is immutable", "list is immutable", "both are immutable", "neither is iterable"], 0),
        lambda i: (f"In dict d, d.get('k', {i%5}) returns what if 'k' missing?",
                   [str(i%5), "KeyError", "None always", "False"], 0),
        lambda i: (f"Which copies a list shallowly (v{i})?",
                   ["list(a)", "copy.deepcopy(a)", "a is b", "set(a)"], 0),
        lambda i: (f"f-strings were added in which Python major version?",
                   ["3.6", "3.3", "2.7", "3.2"], 0),
        lambda i: (f"Which statement about context managers is correct (case {i})?",
                   ["They use __enter__ and __exit__", "They must be classes only", "They auto-retry exceptions", "They disable GC"], 0),
    ]
    # Hard
    h = [
        lambda i: ("Which is TRUE about the GIL in CPython?",
                   ["It prevents multiple native threads executing Python bytecode at once",
                    "It prevents I/O concurrency",
                    "It doesn't affect CPU-bound code",
                    "It exists only in PyPy"], 0),
        lambda i: ("In Python 3.7+, dict preserves:",
                   ["insertion order by language guarantee", "random order", "hash order only", "CPython-only behavior"], 0),
        lambda i: ("What does **kwargs collect in a function call?",
                   ["arbitrary keyword args into a dict", "positional args into a list", "required-only args", "annotations"], 0),
        lambda i: ("Which is the correct way to make an object usable with 'with'?",
                   ["define __enter__ and __exit__", "define __iter__ and __next__", "define __aenter__ only", "inherit from io.IOBase"], 0),
    ]
    return e, m, h

def _sql_templates():
    e = [
        lambda i: ("Which JOIN returns rows present in both tables?",
                   ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN"], 0),
        lambda i: ("Which clause filters after GROUP BY?",
                   ["HAVING", "WHERE", "ORDER BY", "LIMIT"], 0),
        lambda i: ("UNION vs UNION ALL:",
                   ["UNION removes duplicates; UNION ALL doesn't",
                    "Both remove duplicates", "UNION ALL removes duplicates", "Neither can combine"], 0),
        lambda i: (f"Which column type is best for identifiers with no arithmetic (q{i})?",
                   ["VARCHAR", "FLOAT", "DECIMAL for ints", "BOOLEAN"], 0),
        lambda i: ("Which function returns first non-NULL value?",
                   ["COALESCE", "NVL2", "ISNULL", "IFNULL only"], 0),
        lambda i: ("Which predicate can leverage BTREE index well?",
                   ["WHERE col BETWEEN ? AND ?", "WHERE col LIKE '%abc%'", "ORDER BY RANDOM()", "WHERE func(col)=1"], 0),
    ]
    m = [
        lambda i: ("ROW_NUMBER() vs RANK():",
                   ["RANK() allows ties with gaps; ROW_NUMBER() is unique",
                    "They are identical", "ROW_NUMBER() ties", "RANK() unique no gaps"], 0),
        lambda i: ("Composite index (a,b): which benefits most?",
                   ["WHERE a=? AND b=?", "WHERE b=?", "ORDER BY b without a", "WHERE b>? AND a=? only"], 0),
        lambda i: ("EXISTS vs IN performance generally:",
                   ["EXISTS is good for correlated subqueries", "IN is always faster", "Both identical always", "EXISTS returns rows not booleans"], 0),
        lambda i: (f"Which statement is true about NULL in SQL (set {i})?",
                   ["NULL <> 0 and NULL <> ''", "NULL = 0", "NULL sorts before everything always", "COUNT(col) counts NULLs"], 0),
        lambda i: ("Primary key implies:",
                   ["UNIQUE + NOT NULL", "AUTO INCREMENT", "FOREIGN KEY", "CLUSTERED index always"], 0),
        lambda i: ("Window functions:",
                   ["operate on a partition of rows and don't collapse result",
                    "always collapse rows", "only work with GROUP BY", "require DISTINCT"], 0),
    ]
    h = [
        lambda i: ("Isolation level that prevents non-repeatable reads (may allow phantoms):",
                   ["REPEATABLE READ", "READ COMMITTED", "READ UNCOMMITTED", "SERIALIZABLE"], 0),
        lambda i: ("3NF primarily removes:",
                   ["transitive dependencies", "all FDs", "partial deps only", "need for keys"], 0),
        lambda i: ("Foreign key ON DELETE CASCADE means:",
                   ["child rows are deleted when parent is deleted",
                    "parent deleted when child deleted", "deletes prevented", "sets child to default always"], 0),
        lambda i: ("Covering index is:",
                   ["an index containing all columns required by the query",
                    "a clustered index", "a bitmap index", "a hash index"], 0),
    ]
    return e, m, h

def _dj_templates():
    e = [
        lambda i: ("Which command applies migrations?",
                   ["python manage.py migrate", "python manage.py makemigrations", "collectstatic", "runserver"], 0),
        lambda i: ("select_related is best for:",
                   ["following ForeignKey joins", "ManyToMany prefetch", "raw SQL only", "window functions"], 0),
        lambda i: ("Collect static for production:",
                   ["python manage.py collectstatic", "Django does it automatically", "STATIC_DEBUG=1", "runserver"], 0),
        lambda i: (f"Django settings module env var name (v{i})?",
                   ["DJANGO_SETTINGS_MODULE", "DJANGO_CONFIG", "DJANGO_ENV", "SETTINGS_MODULE"], 0),
        lambda i: ("Which field auto-adds created timestamp?",
                   ["DateTimeField(auto_now_add=True)", "DateTimeField(auto_now=True)", "TimeField()", "DurationField()"], 0),
        lambda i: ("Which cache backend is local memory?",
                   ["LocMemCache", "FileBasedCache", "DatabaseCache", "Redis only"], 0),
    ]
    m = [
        lambda i: ("prefetch_related is best for:",
                   ["ManyToMany / reverse FK collections", "ForeignKey only", "select_for_update", "defer()"], 0),
        lambda i: ("Unique pair constraint in models:",
                   ["UniqueConstraint(fields=['a','b']) or unique_together", "primary_key=True on both", "db_index only", "constraints not needed"], 0),
        lambda i: ("QuerySets are:",
                   ["lazy until evaluated", "eager by default", "always cached forever", "evaluated on each filter()"], 0),
        lambda i: ("ModelForm save(commit=False) lets you:",
                   ["modify instance before saving", "skip validation", "create formset", "generate migration"], 0),
        lambda i: ("Which improves N+1 queries on M2M?",
                   ["prefetch_related", "select_related", "only()", "iterator()"], 0),
        lambda i: ("How to do atomic transaction?",
                   ["with transaction.atomic():", "atomic=True on model", "settings.ATOMIC", "no support"], 0),
    ]
    h = [
        lambda i: ("Middleware order:",
                   ["top→down on request, reverse on response", "order doesn't matter", "only first runs", "only last runs"], 0),
        lambda i: ("post_save signal fires:",
                   ["after instance is saved", "before save", "only on create", "only on update"], 0),
        lambda i: ("annotate vs aggregate:",
                   ["annotate adds per-row values; aggregate collapses to one result",
                    "both collapse to one row", "both per-row only", "neither uses GROUP BY"], 0),
        lambda i: ("select_for_update requires:",
                   ["transaction and supported DB", "SQLite only", "MyISAM engine", "no transaction"], 0),
    ]
    return e, m, h

def _drf_templates():
    e = [
        lambda i: ("Which viewset provides list/create/retrieve/update/destroy?",
                   ["ModelViewSet", "ViewSet", "APIView", "GenericAPIView"], 0),
        lambda i: ("Cross-field validation goes in:",
                   ["Serializer.validate(self, attrs)", "validate_<field>", "perform_create", "dispatch"], 0),
        lambda i: ("Header typically carrying JWT:",
                   ["Authorization: Bearer <token>", "X-Auth", "Cookie: sessionid", "X-Api-Key"], 0),
        lambda i: ("Which pagination is page-based?",
                   ["PageNumberPagination", "LimitOffsetPagination", "CursorPagination", "NoPagination"], 0),
        lambda i: (f"Which renderer returns JSON by default (r{i})?",
                   ["JSONRenderer", "BrowsableAPIRenderer", "TemplateHTMLRenderer", "StaticHTMLRenderer"], 0),
        lambda i: ("To access request in serializer:",
                   ["self.context['request']", "self.request", "Serializer.request", "settings.REQUEST"], 0),
    ]
    m = [
        lambda i: ("@action(detail=True) on a ViewSet creates:",
                   ["a detail route like /<pk>/do/", "a list route", "a router registrar", "a throttle scope"], 0),
        lambda i: ("Permissions are checked:",
                   ["before calling the handler", "after serialization", "only on POST", "only unsafe methods"], 0),
        lambda i: ("Throttling per-view is set via:",
                   ["throttle_classes on the view", "permission_classes only", "parser_classes", "authentication_classes"], 0),
        lambda i: ("HyperlinkedModelSerializer requires:",
                   ["a 'url' field and proper view_name/routers", "only pk field", "APIView only", "no router"], 0),
        lambda i: ("Parser for multipart forms:",
                   ["MultiPartParser", "JSONParser", "FileParser", "BaseParser"], 0),
        lambda i: ("Renderer for browsable UI:",
                   ["BrowsableAPIRenderer", "AdminRenderer", "JSONRenderer", "TemplateRenderer"], 0),
    ]
    h = [
        lambda i: ("Nested writes typically require:",
                   ["overriding create()/update()", "nothing special", "throttles", "schema generation"], 0),
        lambda i: ("Which is TRUE about GenericAPIView?",
                   ["provides core behavior (queryset/serializer_class/get_object)", "renders HTML only", "requires routers", "deprecated"], 0),
        lambda i: ("CursorPagination advantages include:",
                   ["stable ordering & opaque cursors", "offset arithmetic", "random order", "ties to page number"], 0),
        lambda i: ("Schema generation tool in DRF core:",
                   ["drf-spectacular or coreapi/openapi integrations", "only swagger-ui builtin", "not supported", "admin only"], 0),
    ]
    return e, m, h

def _react_templates():
    e = [
        lambda i: ("Which hook adds local state to a function component?",
                   ["useState", "useEffect", "useMemo", "useRef"], 0),
        lambda i: ("The 'key' prop in lists helps React:",
                   ["track item identity across renders", "style items", "force rerenders", "handle events"], 0),
        lambda i: ("Which prop passes read-only data from parent to child?",
                   ["props", "state", "context", "ref"], 0),
        lambda i: ("Which hook runs after first render when deps=[]?",
                   ["useEffect", "useMemo", "useCallback", "useLayoutEffect only"], 0),
        lambda i: (f"Which is TRUE about fragments (v{i})?",
                   ["<>...</> lets you group children without extra DOM", "They must have a key always", "They are comments", "They wrap in <div>"], 0),
        lambda i: ("Event handler naming convention in JSX:",
                   ["onClick, onChange (camelCase)", "onclick", "on-click", "handleClick attr"], 0),
    ]
    m = [
        lambda i: ("Controlled component means:",
                   ["value is driven by React state via props", "DOM controls its own value", "refs required", "class only"], 0),
        lambda i: ("Lifting state up solves:",
                   ["sharing state between siblings via common parent", "global state only", "SSR only", "styling"], 0),
        lambda i: ("useCallback vs useMemo:",
                   ["useCallback memoizes a function; useMemo memoizes a value",
                    "they are identical", "both memoize values", "neither takes deps"], 0),
        lambda i: ("When mapping arrays, keys should be:",
                   ["stable and unique among siblings", "array index always", "random()", "component name"], 0),
        lambda i: ("Which library commonly manages global state?",
                   ["Redux Toolkit", "Requests", "Axios", "Lodash"], 0),
        lambda i: ("React Router element to declare a route:",
                   ["<Route>", "<Switch>", "<Router>", "<Link>"], 0),
    ]
    h = [
        lambda i: ("React.memo helps by:",
                   ["skipping re-render when props are shallow-equal", "batching updates", "avoiding reconciliation", "server components only"], 0),
        lambda i: ("Reconciliation primarily compares:",
                   ["element trees by type and keys", "raw HTML strings", "only state", "only DOM attrs"], 0),
        lambda i: ("Context API is used to:",
                   ["avoid prop drilling by providing values down the tree", "manage DOM events", "CSS scoping", "only Redux"], 0),
        lambda i: ("useLayoutEffect vs useEffect:",
                   ["useLayoutEffect runs after DOM mutations but before paint", "they are identical", "useEffect runs before render", "layout effect is server-only"], 0),
    ]
    return e, m, h

def _seed_topic(topic, tmpl_fn, e_count, m_count, h_count):
    e, m, h = tmpl_fn()
    items = []
    items += _gen_items(e, e_count)
    items += _gen_items(m, m_count)
    items += _gen_items(h, h_count)
    for (text, opts, correct) in items:
        _mk_q(topic, Difficulty.EASY if len(opts) and (text, opts, correct) in items[:e_count] else None, "", [], 0)  # placeholder
    # The above quick approach isn't ideal; recreate cleanly below using per-bucket loops:

def _seed_topic_clean(topic, tmpl_fn, e_count, m_count, h_count):
    e, m, h = tmpl_fn()
    for (text, opts, correct) in _gen_items(e, e_count):
        _mk_q(topic, Difficulty.EASY, text, opts, correct)
    for (text, opts, correct) in _gen_items(m, m_count):
        _mk_q(topic, Difficulty.MEDIUM, text, opts, correct)
    for (text, opts, correct) in _gen_items(h, h_count):
        _mk_q(topic, Difficulty.HARD, text, opts, correct)

def _seed_300_questions():
    """
    Create exactly 300 MCQs:
      - 5 topics * 60 each
      - Per topic: 24 easy, 24 medium, 12 hard
    """
    per_topic = {"easy": 24, "medium": 24, "hard": 12}
    _seed_topic_clean("python", _py_templates, per_topic["easy"], per_topic["medium"], per_topic["hard"])
    _seed_topic_clean("sql", _sql_templates, per_topic["easy"], per_topic["medium"], per_topic["hard"])
    _seed_topic_clean("django", _dj_templates, per_topic["easy"], per_topic["medium"], per_topic["hard"])
    _seed_topic_clean("drf", _drf_templates, per_topic["easy"], per_topic["medium"], per_topic["hard"])
    _seed_topic_clean("react", _react_templates, per_topic["easy"], per_topic["medium"], per_topic["hard"])

# -------------------
# MAIN seeding routine
# -------------------
def run():
    print("=== RESET (exams-only) → seed 3-stage quiz (20m stages & 20m breaks) ===")
    now = timezone.now()

    # 0) Wipe exam runtime/config tables AND question bank
    with transaction.atomic():
        AttemptAnswer.objects.all().delete()
        StageAttemptItem.objects.all().delete()
        QuizStageAttempt.objects.all().delete()
        QuizAttempt.objects.all().delete()

        LeaderboardEntry.objects.all().delete()
        StageAdmission.objects.all().delete()
        StageQuestion.objects.all().delete()
        StageRandomRule.objects.all().delete()
        QuizStage.objects.all().delete()
        AccessToken.objects.all().delete()
        Quiz.objects.all().delete()

        QuestionOption.objects.all().delete()
        Question.objects.all().delete()

    print("Cleared exams data + question bank (kept users, anti-cheat logs, etc.).")

    # 1) Seed 300 realistic MCQs
    _seed_300_questions()
    bank_size = Question.objects.filter(is_active=True).count()
    print("Bank size (active):", bank_size)

    # 2) Quiz & stages — 20m each, 20m breaks, stages 2 & 3 gated
    # Quiz-level difficulty totals should match bank totals for ratios
    easy_total, med_total, hard_total = 120, 120, 60  # 300 total

    s1_start = now
    s1_end   = now + timedelta(minutes=20)

    s2_start = now + timedelta(minutes=40)   # 20m break after S1
    s2_end   = now + timedelta(minutes=60)

    s3_start = now + timedelta(minutes=80)   # 20m break after S2
    s3_end   = now + timedelta(minutes=100)

    quiz, _ = Quiz.objects.update_or_create(
        slug="quiz-3stage-20m-300q",
        defaults=dict(
            title="Tech Stack Quiz (3 stages, 20m each)",
            description="Python, SQL, Django, DRF, React — auto-picked questions; big bank (300).",
            subspecialty="general",
            easy_count=easy_total, medium_count=med_total, hard_count=hard_total,
            start_at=s1_start,
            end_at=s3_end + timedelta(minutes=10),
            duration_seconds=60*120,  # overall cap; per-stage is enforced on stages
            pass_threshold_percent=60,
            max_attempts_per_user=1,
            question_count=easy_total + med_total + hard_total,  # 300 (for ratio math)
            shuffle_questions=True,
            shuffle_options=True,
            require_fullscreen=True,
            lock_on_tab_switch=True,
            prerequisite_tutorial=None,
            is_active=True,
        )
    )

    # Stage question counts: 12, 13, 15 (within 10–15)
    s1, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=1,
        defaults=dict(
            title="Stage 1", description="Round 1",
            start_at=s1_start, end_at=s1_end,
            duration_seconds=20*60,
            question_count=12,
            shuffle_questions=None, shuffle_options=None,
            is_current=True,
            requires_admission=False,
        )
    )
    s2, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=2,
        defaults=dict(
            title="Stage 2", description="Round 2",
            start_at=s2_start, end_at=s2_end,
            duration_seconds=20*60,
            question_count=13,
            shuffle_questions=None, shuffle_options=None,
            is_current=False,
            requires_admission=True,   # gated
        )
    )
    s3, _ = QuizStage.objects.update_or_create(
        quiz=quiz, order=3,
        defaults=dict(
            title="Stage 3", description="Round 3",
            start_at=s3_start, end_at=s3_end,
            duration_seconds=20*60,
            question_count=15,
            shuffle_questions=None, shuffle_options=None,
            is_current=False,
            requires_admission=True,   # gated
        )
    )

    # Ensure only Stage 1 is current
    QuizStage.objects.filter(quiz=quiz).exclude(pk=s1.pk).update(is_current=False)

    # Random rules: no filters → whole bank; count = stage.question_count
    for st in (s1, s2, s3):
        StageRandomRule.objects.update_or_create(
            stage=st,
            defaults=dict(count=st.question_count, tags_any=[], difficulties=[], subspecialties=[], region_hints=[])
        )

    # Make this the ONLY active quiz
    Quiz.objects.exclude(pk=quiz.pk).update(is_active=False)

    print("Active quiz:", quiz.slug)
    print("Stages:",
          list(QuizStage.objects.filter(quiz=quiz).order_by("order")
               .values("order","title","start_at","end_at","question_count",
                       "duration_seconds","is_current","requires_admission")))
    print("=== DONE ===")

# Run via:
# python manage.py shell -c "from scripts.reset_and_seed_3stage_20m_300q import run; run()"
if __name__ == "__main__":
    run()
