"""Deterministic, tenant-scoped product classification.

The classifier is deliberately conservative. It prefers explicit phrases,
uses exclusions to resolve ambiguous Hebrew product names, and abstains when
the evidence is weak instead of forcing an incorrect category.
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

HARD_RULES = (
    ("ירקות", ("תפוח אדמה", "תפוחי אדמה", "תפו אדמה")),
    ("רטבים ותבלינים", ("פלפל שחור", "פלפל לבן", "פלפל גרוס", "פלפל אדום טחון")),
    ("שימורים", ("טונה בקופסה", "טונה בשימורים", "טונה משומרת", "תירס בקופסה", "תירס משומר")),
    ("קפואים", ("שניצל עוף קפוא", "שניצל קפוא", "אפונה קפואה", "שעועית קפואה", "ירקות קפואים", "פירות קפואים")),
    ("חד פעמי", ("צלחת חד פעמית", "צלחות חד פעמיות", "כוס חד פעמית", "כוסות חד פעמיות", "מזלגות חד פעמיים", "כפיות חד פעמיות")),
    ("עוף", ("שניצל עוף", "חזה עוף", "כנפי עוף", "פרגית", "נאגטס עוף")),
)

PRIORITY_RULES = [
    ("קפואים", ("שניצל עוף קפוא", "שניצל קפוא", "בורקס קפוא", "בורקסים קפואים", "אפונה קפואה", "שעועית קפואה", "ירקות קפואים", "פירות קפואים", "ציפס קפוא", "צ'יפס קפוא", "קפוא", "קפואים", "קפואות")),
    ("שימורים", ("טונה בשימורים", "טונה בקופסה", "טונה משומרת", "תירס בקופסה", "תירס משומר", "שעועית שימורים", "קופסת שימורים", "קופסאות שימורים", "שימורים", "שימור", "זיתים", "זית", "חמוצים", "חמוץ")),
    ("חד פעמי", ("צלחות חד פעמיות", "צלחת חד פעמית", "כוסות חד פעמיות", "כוס חד פעמית", "מזלגות חד פעמיים", "כפיות חד פעמיות", "סכום חד פעמי", 'סכו"ם חד פעמי', "חד פעמי", "חדפ", "מפיות", "קשיות")),
    ("רטבים ותבלינים", ("פלפל שחור", "פלפל לבן", "פלפל גרוס", "פלפל אדום טחון", "פפריקה", "כמון", "כורכום", "מלח", "תבלין", "תבלינים", "קטשופ", "מיונז", "חרדל", "רוטב", "רטבים", "רוטב סויה", "שום כתוש", "טחינה", "חומוס")),
    ("עוף", ("שניצל עוף", "חזה עוף", "כרעיים", "כנפי עוף", "כנפיים", "פרגית", "פרגיות", "נאגטס עוף", "פסטרמה עוף", "עוף", "עופות")),
    ("בשר", ("בשר טחון", "טחון בקר", "אסאדו", "צלי בקר", "סטייק", "סינטה", "אנטריקוט", "המבורגר בקר", "קבב", "קבבים", "קציצה", "קציצות", "בשר", "בשרים")),
    ("דגים", ("פילה דג", "פילה סלמון", "סלמון", "אמנון", "מושט", "קרפיון", "סרדין", "סרדינים", "דג", "דגים", "טונה")),
    ("מוצרי חלב", ("מוצרי חלב", "מוצר חלב", "גבינת", "גבינה", "גבינות", "קוטג", "יוגורט", "יוגורטים", "שמנת", "לבנה", "מעדן", "מעדנים", "חמאה", "אשל", "ריוויון", "חלב")),
    ("ירקות", ("תפוחי אדמה", "תפוח אדמה", "תפו אדמה", "עגבניות", "עגבניה", "מלפפונים", "מלפפון", "גזרים", "גזר", "בצל", "בצלים", "פלפלים", "פלפל אדום", "פלפל ירוק", "כרוב", "כרובים", "חסה", "קישוא", "קישואים", "ברוקולי", "כרובית", "סלק", "צנונית", "בטטה", "בטטות", "חציל", "חצילים", "ירקות", "ירק")),
    ("פירות", ("תפוחים", "תפוח", "בננות", "בננה", "תפוזים", "תפוז", "קלמנטינות", "קלמנטינה", "אגסים", "אגס", "ענבים", "אבטיח", "מלון", "אפרסקים", "אפרסק", "שזיפים", "שזיף", "מנגו", "קיווי", "אננס", "פירות", "פרי")),
    ("מזון יבש", ("דגני בוקר", "קורנפלקס", "שיבולת שועל", "אורז", "פסטה", "ספגטי", "קוסקוס", "קמח", "סוכר", "קטניות", "עדשים", "בורגול", "פתיתים", "גריסים", "מזון יבש")),
    ("מאפים ולחמים", ("לחם", "לחמים", "לחמניה", "לחמניות", "פיתה", "פיתות", "בגט", "בגטים", "עוגה", "עוגות", "מאפה", "מאפים", "קרואסון", "קרואסונים", "חלה", "חלות")),
    ("משקאות", ("מים מינרליים", "מיץ תפוזים", "מיץ", "מיצים", "מים", "סודה", "קולה", "שתיה", "שתייה", "משקה", "משקאות", "קפה נמס", "קפה", "תה", "שוקו")),
    ("חטיפים", ("במבה", "ביסלי", "ציפס חטיף", "צ'יפס חטיף", "חטיף", "חטיפים", "קרקר", "קרקרים", "בייגלה", "פופקורן")),
    ("ממתקים", ("שוקולד", "שוקולדים", "סוכריה", "סוכריות", "ממתק", "ממתקים", "וופל", "וופלים", "מרשמלו", "סוכריות גומי", "גומי", "טופי")),
    ("ניקיון", ("אקונומיקה", "נוזל כלים", "סבון כלים", "אבקת כביסה", "מרכך כביסה", "מרכך", "מסיר שומנים", "שקיות אשפה", "שקית אשפה", "מטליות", "נייר ניקוי", "ניקוי", "ניקיון", "סבון")),
    ("ציוד מטבח", ("קרש חיתוך", "כלי מטבח", "תבנית", "קערה", "קערות", "מלקחיים", "פותחן", "כף הגשה", "מחבת", "סיר", "סכין", "צלחות", "צלחת", "כוס", "כוסות", "ציוד מטבח")),
]

EXCLUSIONS = {
    "ירקות": ("פלפל שחור", "פלפל לבן", "פלפל גרוס", "פלפל אדום טחון"),
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
        return (db.session.query(ProductClassificationFeedback).filter_by(tenant_id=tenant_id, normalized_name=normalized_name).order_by(ProductClassificationFeedback.created_at.desc(), ProductClassificationFeedback.id.desc()).first())

    @staticmethod
    def _similar_feedback(tenant_id: int, normalized_name: str):
        recent = (db.session.query(ProductClassificationFeedback).filter_by(tenant_id=tenant_id).order_by(ProductClassificationFeedback.created_at.desc(), ProductClassificationFeedback.id.desc()).limit(1000).all())
        best = None
        best_score = 0.0
        for feedback in recent:
            score = SequenceMatcher(None, normalized_name, feedback.normalized_name).ratio()
            if score > best_score:
                best_score = score
                best = feedback
        return best, best_score

    def classify(self, tenant_id: int, product_name: str):
        normalized = normalize_product_name(product_name)
        if not normalized:
            raise BadRequest("Product name is required for classification")
        feedback = self._latest_feedback(tenant_id, normalized)
        if feedback:
            return {"category": feedback.actual_category, "confidence": 1.0, "source": "LEARNED", "reason": "התאמה להחלטה קודמת של משתמש"}
        for category, phrases in HARD_RULES:
            matches = [phrase for phrase in phrases if _phrase_present(normalized, phrase)]
            if matches:
                return {"category": category, "confidence": 0.99, "source": "RULES", "reason": "התאמה מדויקת: " + ", ".join(matches[:3])}
        similar_feedback, similarity = self._similar_feedback(tenant_id, normalized)
        if similar_feedback is not None and similarity >= 0.95:
            return {"category": similar_feedback.actual_category, "confidence": round(min(0.99, similarity), 4), "source": "LEARNED", "reason": f"התאמה חזקה למוצר שסווג בעבר ({similarity:.0%})"}
        candidates = []
        for priority, (category, phrases) in enumerate(PRIORITY_RULES):
            if any(_phrase_present(normalized, excluded) for excluded in EXCLUSIONS.get(category, ())):
                continue
            matches = [phrase for phrase in phrases if _phrase_present(normalized, phrase)]
            if not matches:
                continue
            score = max((3.0 + 1.2 * len(normalize_product_name(p).split()) for p in matches), default=0.0)
            score += min(1.5, max(0, len(matches) - 1) * 0.35)
            candidates.append((score, -priority, category, matches))
        if not candidates:
            return {"category": None, "confidence": 0.0, "source": "RULES", "reason": "לא נמצאה התאמה מספקת; המוצר דורש בדיקה"}
        candidates.sort(reverse=True)
        best_score, _, category, matches = candidates[0]
        second_score = candidates[1][0] if len(candidates) > 1 else 0.0
        margin = best_score - second_score
        if best_score < 3.0 or (len(candidates) > 1 and margin < 1.0):
            return {"category": None, "confidence": 0.0, "source": "RULES", "reason": "נמצאו כמה אפשרויות או שאין מספיק ודאות; המוצר דורש בדיקה"}
        confidence = min(0.99, 0.62 + min(best_score, 7.0) * 0.04 + min(margin, 4.0) * 0.06)
        return {"category": category, "confidence": round(confidence, 4), "source": "RULES", "reason": "התאמות: " + ", ".join(matches[:4])}

    def record_feedback(self, tenant_id: int, user_id: int, product_id: int, product_name: str, actual_category: str, predicted_category=None, confidence=None):
        actual_category = (actual_category or "").strip()
        normalized_name = normalize_product_name(product_name)
        if actual_category not in CATEGORIES:
            raise BadRequest("Invalid product category")
        if not normalized_name:
            raise BadRequest("Product name is required for classification")
        feedback = ProductClassificationFeedback(tenant_id=tenant_id, product_id=product_id, normalized_name=normalized_name, predicted_category=predicted_category, actual_category=actual_category, source="USER", confidence=confidence, created_by=user_id)
        db.session.add(feedback)
        return feedback

    @staticmethod
    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, normalize_product_name(a), normalize_product_name(b)).ratio()
