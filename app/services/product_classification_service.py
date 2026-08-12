"""Tenant-scoped deterministic product classifier.

The classifier deliberately prefers specific product phrases over individual
words. Ambiguous names abstain instead of guessing, and user feedback always
wins over automatic rules.
"""
import re
from difflib import SequenceMatcher

from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models.product_classification_feedback import ProductClassificationFeedback

CATEGORIES = (
    "מוצרי חלב", "ירקות", "פירות", "בשר", "עוף", "דגים", "קפואים",
    "שימורים", "מזון יבש", "מאפים ולחמים", "משקאות", "חטיפים", "ממתקים",
    "רטבים ותבלינים", "חד פעמי", "ניקיון", "ציוד מטבח", "אחר",
)

# Specific phrases must be evaluated before generic words. This prevents
# products such as "אבקת בצל" from being classified as vegetables merely
# because the raw name contains "בצל".
SEMANTIC_RULES = (
    ("מזון יבש", (
        "אבקת בצל", "אבקת שום", "אבקת אפיה", "אבקת אפייה", "אבקת מרק",
        "אבקת קקאו", "אבקת סוכר", "אבקה להכנת פירה", "אבקה להכנת טמפורה",
        "אבקה להכנת פנקייק", "תערובת להכנת פירה", "תערובת להכנת טמפורה",
        "תערובת להכנת פנקייק", "תערובת אפיה", "תערובת אפייה", "פירורי לחם",
        "קמח", "אורז", "פסטה", "ספגטי", "קוסקוס", "פתיתים", "בורגול",
        "עדשים", "גריסים", "שיבולת שועל", "דגני בוקר", "קורנפלקס",
        "סוכר", "מזון יבש",
    )),
    ("ממתקים", (
        "אבקת נוגט", "אבקת שוקולד", "שוקולד", "שוקולדים", "סוכריה",
        "סוכריות", "ממתק", "ממתקים", "וופל", "וופלים", "מרשמלו",
        "סוכריות גומי", "טופי",
    )),
    ("משקאות", (
        "אבקה להכנת שוקו", "אבקה להכנת שוקולד", "אבקה להכנת משקה",
        "אבקה להכנת לימונדה", "אבקה להכנת אייס קפה", "אבקה להכנת קפה",
        "תרכיז למשקה", "תרכיז פטל", "תרכיז תפוז", "מיץ", "מיצים",
        "מים מינרליים", "מים", "סודה", "קולה", "שתיה", "שתייה",
        "משקה", "משקאות", "קפה נמס", "תה", "שוקו",
    )),
    ("מוצרי חלב", (
        "גבינה צהובה", "גבינה לבנה", "גבינת שמנת", "גבינת קוטג", "קוטג",
        "יוגורט", "יוגורטים", "מעדן חלב", "מעדן שוקולד", "מעדן וניל",
        "מילקי", "גמדים", "שמנת חמוצה", "שמנת מתוקה", "לבנה", "חמאה",
        "אשל", "ריוויון", "חלב", "מוצרי חלב", "מוצר חלב",
    )),
    ("רטבים ותבלינים", (
        "פלפל שחור", "פלפל לבן", "פלפל גרוס", "פלפל אדום טחון", "אבקת שום",
        "פפריקה", "כמון", "כורכום", "מלח", "תבלין", "תבלינים", "קטשופ",
        "מיונז", "חרדל", "רוטב סויה", "רוטב", "רטבים", "שום כתוש",
        "טחינה", "חומוס",
    )),
    ("שימורים", (
        "טונה בקופסה", "טונה בשימורים", "טונה משומרת", "תירס בקופסה",
        "תירס משומר", "שעועית שימורים", "קופסת שימורים", "קופסאות שימורים",
        "שימורים", "זיתים", "חמוצים",
    )),
    ("קפואים", (
        "שניצל עוף קפוא", "שניצל קפוא", "בורקס קפוא", "בורקסים קפואים",
        "אפונה קפואה", "שעועית קפואה", "ירקות קפואים", "פירות קפואים",
        "ציפס קפוא", "צ'יפס קפוא", "קפוא", "קפואים", "קפואות",
    )),
    ("חד פעמי", (
        "צלחת חד פעמית", "צלחות חד פעמיות", "כוס חד פעמית", "כוסות חד פעמיות",
        "מזלגות חד פעמיים", "כפיות חד פעמיות", "סכום חד פעמי", 'סכו"ם חד פעמי',
        "חד פעמי", "חדפ", "מפיות", "קשיות",
    )),
    ("ניקיון", (
        "אבקת כביסה", "נוזל כביסה", "מרכך כביסה", "נוזל כלים", "סבון כלים",
        "אקונומיקה", "מסיר שומנים", "שקיות אשפה", "שקית אשפה", "מטליות",
        "נייר ניקוי", "ניקוי", "ניקיון",
    )),
    ("ציוד מטבח", (
        "קרש חיתוך", "כלי מטבח", "תבנית אפיה", "תבנית אפייה", "קערה",
        "קערות", "מלקחיים", "פותחן", "כף הגשה", "מחבת", "סיר", "סכין",
        "ציוד מטבח",
    )),
    ("עוף", (
        "שניצל עוף", "חזה עוף", "כרעיים", "כנפי עוף", "כנפיים", "פרגית",
        "פרגיות", "נאגטס עוף", "פסטרמה עוף", "עוף", "עופות",
    )),
    ("בשר", (
        "בשר טחון", "טחון בקר", "אסאדו", "צלי בקר", "סטייק", "סינטה",
        "אנטריקוט", "המבורגר בקר", "קבב", "קבבים", "קציצה", "קציצות",
        "בשר", "בשרים",
    )),
    ("דגים", (
        "פילה דג", "פילה סלמון", "סלמון", "אמנון", "מושט", "קרפיון",
        "סרדין", "סרדינים", "דגים", "דג",
    )),
    ("ירקות", (
        "תפוחי אדמה", "תפוח אדמה", "תפו אדמה", "עגבניות", "עגבניה",
        "מלפפונים", "מלפפון", "גזרים", "גזר", "בצל", "בצלים", "פלפלים",
        "פלפל אדום", "פלפל ירוק", "כרוב", "כרובים", "חסה", "קישוא",
        "קישואים", "ברוקולי", "כרובית", "סלק", "צנונית", "בטטה", "בטטות",
        "חציל", "חצילים", "ירקות", "ירק",
    )),
    ("פירות", (
        "תפוחים", "תפוח", "בננות", "בננה", "תפוזים", "תפוז", "קלמנטינות",
        "קלמנטינה", "אגסים", "אגס", "ענבים", "אבטיח", "מלון", "אפרסקים",
        "אפרסק", "שזיפים", "שזיף", "מנגו", "קיווי", "אננס", "פירות", "פרי",
    )),
    ("מאפים ולחמים", (
        "לחם", "לחמים", "לחמניה", "לחמניות", "פיתה", "פיתות", "בגט", "בגטים",
        "עוגה", "עוגות", "מאפה", "מאפים", "קרואסון", "קרואסונים", "חלה", "חלות",
    )),
    ("חטיפים", (
        "במבה", "ביסלי", "ציפס חטיף", "צ'יפס חטיף", "חטיף", "חטיפים", "קרקר",
        "קרקרים", "בייגלה", "פופקורן",
    )),
)

EXCLUSIONS = {
    "ירקות": ("אבקת בצל", "אבקת שום", "פלפל שחור", "פלפל לבן", "פלפל גרוס", "פלפל אדום טחון"),
    "פירות": ("תפוח אדמה", "תפוחי אדמה", "תפו אדמה"),
    "דגים": ("טונה בשימורים", "טונה בקופסה", "טונה משומרת"),
    "עוף": ("שניצל קפוא", "שניצל עוף קפוא"),
    "ציוד מטבח": ("צלחת חד פעמית", "צלחות חד פעמיות", "כוס חד פעמית", "כוסות חד פעמיות"),
}


def normalize_product_name(name: str) -> str:
    value = (name or "").strip().casefold()
    value = value.replace("״", '"').replace("׳", "'")
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:ק\"ג|קג|גרם|גר'|ליטר|ל'|מ\"ל|מל|יח')\b", " ", value)
    value = re.sub(r"[^א-תa-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _phrase_present(text: str, phrase: str) -> bool:
    phrase = normalize_product_name(phrase)
    if not phrase:
        return False
    return re.search(r"(?<![א-תa-z0-9])" + re.escape(phrase) + r"(?![א-תa-z0-9])", text) is not None


class ProductClassificationService:
    @staticmethod
    def categories():
        return list(CATEGORIES)

    @staticmethod
    def _latest_feedback(tenant_id: int, normalized_name: str):
        return (
            db.session.query(ProductClassificationFeedback)
            .filter_by(tenant_id=tenant_id, normalized_name=normalized_name)
            .order_by(ProductClassificationFeedback.created_at.desc(), ProductClassificationFeedback.id.desc())
            .first()
        )

    @staticmethod
    def _similar_feedback(tenant_id: int, normalized_name: str):
        recent = (
            db.session.query(ProductClassificationFeedback)
            .filter_by(tenant_id=tenant_id)
            .order_by(ProductClassificationFeedback.created_at.desc(), ProductClassificationFeedback.id.desc())
            .limit(1000).all()
        )
        best = None
        best_score = 0.0
        for feedback in recent:
            score = SequenceMatcher(None, normalized_name, feedback.normalized_name).ratio()
            if score > best_score:
                best_score, best = score, feedback
        return best, best_score

    def classify(self, tenant_id: int, product_name: str):
        normalized = normalize_product_name(product_name)
        if not normalized:
            raise BadRequest("Product name is required for classification")

        feedback = self._latest_feedback(tenant_id, normalized)
        if feedback:
            return {"category": feedback.actual_category, "confidence": 1.0, "source": "LEARNED", "reason": "התאמה להחלטה קודמת של משתמש"}

        # Exact semantic phrases are stronger than generic token matches.
        semantic_candidates = []
        for priority, (category, phrases) in enumerate(SEMANTIC_RULES):
            matches = [phrase for phrase in phrases if _phrase_present(normalized, phrase)]
            if matches:
                semantic_candidates.append((max(len(normalize_product_name(p).split()) for p in matches), -priority, category, matches))
        if semantic_candidates:
            semantic_candidates.sort(reverse=True)
            score, _, category, matches = semantic_candidates[0]
            second = semantic_candidates[1][0] if len(semantic_candidates) > 1 else 0
            if len(semantic_candidates) == 1 or score > second:
                return {"category": category, "confidence": 0.97 if score >= 3 else 0.94, "source": "RULES", "reason": "ביטוי מוצר מזוהה: " + ", ".join(matches[:3])}

        similar_feedback, similarity = self._similar_feedback(tenant_id, normalized)
        if similar_feedback is not None and similarity >= 0.95:
            return {"category": similar_feedback.actual_category, "confidence": round(min(0.99, similarity), 4), "source": "LEARNED", "reason": f"התאמה חזקה למוצר שסווג בעבר ({similarity:.0%})"}

        # Generic fallback is intentionally conservative.
        generic = (
            ("מוצרי חלב", ("גבינה", "גבינות", "יוגורט", "שמנת", "חלב", "חמאה", "מעדן", "קוטג")),
            ("קפואים", ("קפוא", "קפואים", "קפואות")),
            ("שימורים", ("שימורים", "משומר")),
            ("עוף", ("עוף", "פרגית")),
            ("בשר", ("בשר", "סטייק", "קבב")),
            ("דגים", ("דג", "דגים", "סלמון", "אמנון", "מושט")),
            ("ירקות", ("עגבניה", "מלפפון", "גזר", "בצל", "תפוח אדמה", "בטטה")),
            ("פירות", ("תפוח", "בננה", "תפוז", "אגס", "ענבים", "מנגו")),
        )
        candidates = []
        for priority, (category, phrases) in enumerate(generic):
            if any(_phrase_present(normalized, excluded) for excluded in EXCLUSIONS.get(category, ())):
                continue
            matches = [phrase for phrase in phrases if _phrase_present(normalized, phrase)]
            if matches:
                candidates.append((max(len(normalize_product_name(p).split()) for p in matches), -priority, category, matches))
        if len(candidates) == 1:
            _, _, category, matches = candidates[0]
            return {"category": category, "confidence": 0.82, "source": "RULES", "reason": "התאמה כללית: " + ", ".join(matches[:3])}
        return {"category": None, "confidence": 0.0, "source": "RULES", "reason": "אין ודאות מספקת; המוצר דורש בדיקה"}

    def record_feedback(self, tenant_id: int, user_id: int, product_id: int, product_name: str, actual_category: str, predicted_category=None, confidence=None):
        actual_category = (actual_category or "").strip()
        normalized_name = normalize_product_name(product_name)
        if actual_category not in CATEGORIES:
            raise BadRequest("Invalid product category")
        if not normalized_name:
            raise BadRequest("Product name is required for classification")
        feedback = ProductClassificationFeedback(
            tenant_id=tenant_id, product_id=product_id, normalized_name=normalized_name,
            predicted_category=predicted_category, actual_category=actual_category,
            source="USER", confidence=confidence, created_by=user_id,
        )
        db.session.add(feedback)
        return feedback

    @staticmethod
    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, normalize_product_name(a), normalize_product_name(b)).ratio()
