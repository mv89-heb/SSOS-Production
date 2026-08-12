"""Deterministic product categorization with tenant-scoped learning feedback."""
import re
from difflib import SequenceMatcher

from werkzeug.exceptions import BadRequest, NotFound

from app.extensions import db
from app.models.product_classification_feedback import ProductClassificationFeedback

CATEGORIES = (
    "מוצרי חלב", "ירקות", "פירות", "בשר", "עוף", "דגים", "קפואים",
    "שימורים", "מזון יבש", "מאפים ולחמים", "משקאות", "חטיפים", "ממתקים",
    "רטבים ותבלינים", "חד פעמי", "ניקיון", "ציוד מטבח", "אחר",
)

RULES = {
    "מוצרי חלב": ("חלב", "גבינה", "קוטג", "יוגורט", "שמנת", "לבנה", "מעדן", "חמאה", "אשל"),
    "ירקות": ("עגבניה", "עגבניות", "מלפפון", "גזר", "בצל", "תפוח אדמה", "תפו" , "פלפל", "כרוב", "חסה", "קישוא"),
    "פירות": ("תפוח", "בננה", "תפוז", "קלמנטינה", "אגס", "ענבים", "אבטיח", "מלון", "אפרסק", "שזיף"),
    "בשר": ("בשר", "אסאדו", "צלי", "סטייק", "סינטה", "אנטריקוט", "המבורגר"),
    "עוף": ("עוף", "שניצל עוף", "חזה עוף", "כרעיים", "כנפיים", "פרגית"),
    "דגים": ("דג", "טונה", "סלמון", "אמנון", "מושט", "קרפיון", "סרדין"),
    "קפואים": ("קפוא", "קפואים", "צ'יפס", "בורקס קפוא", "טבעות בצל", "אפונה קפואה"),
    "שימורים": ("שימורים", "תירס בקופסה", "זיתים", "חמוצים", "שעועית שימורים"),
    "מזון יבש": ("אורז", "פסטה", "ספגטי", "קוסקוס", "קמח", "סוכר", "קטניות", "עדשים", "בורגול"),
    "מאפים ולחמים": ("לחם", "לחמניה", "לחמניות", "פיתה", "בגט", "עוגה", "מאפה", "קרואסון"),
    "משקאות": ("מים", "מיץ", "סודה", "קולה", "שתיה", "משקה", "קפה", "תה"),
    "חטיפים": ("במבה", "ביסלי", "חטיף", "צ'יפס חטיף", "קרקרים"),
    "ממתקים": ("שוקולד", "סוכריה", "ממתק", "וופל", "מרשמלו", "גומי"),
    "רטבים ותבלינים": ("קטשופ", "מיונז", "חרדל", "רוטב", "תבלין", "מלח", "פלפל שחור", "פפריקה"),
    "חד פעמי": ("חד פעמי", "כוסות חד", "צלחות חד", "סכו" , "מפיות", "קשיות"),
    "ניקיון": ("אקונומיקה", "נוזל כלים", "אבקת כביסה", "מרכך", "ניקוי", "ניקיון", "סבון", "שקיות אשפה"),
    "ציוד מטבח": ("סיר", "מחבת", "סכין", "קרש חיתוך", "כלי מטבח", "תבנית"),
}


def normalize_product_name(name: str) -> str:
    value = (name or "").strip().casefold()
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:ק\"ג|קג|גרם|גר'|ליטר|ל'|מ\"ל|מל|יח')\b", " ", value)
    value = re.sub(r"[^א-תa-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class ProductClassificationService:
    @staticmethod
    def categories():
        return list(CATEGORIES)

    @staticmethod
    def _feedback_candidates(tenant_id: int):
        rows = db.session.query(ProductClassificationFeedback).filter_by(tenant_id=tenant_id).order_by(ProductClassificationFeedback.created_at.desc()).limit(2000).all()
        return rows

    def classify(self, tenant_id: int, product_name: str):
        normalized = normalize_product_name(product_name)
        if not normalized:
            raise BadRequest("Product name is required for classification")

        # Exact user corrections have priority over generic rules.
        for feedback in self._feedback_candidates(tenant_id):
            if feedback.normalized_name == normalized:
                return {"category": feedback.actual_category, "confidence": 1.0, "source": "LEARNED", "reason": "התאמה להחלטה קודמת של משתמש"}

        scores = []
        for category, keywords in RULES.items():
            matched = [keyword for keyword in keywords if normalize_product_name(keyword) in normalized]
            if matched:
                # Exact phrase is stronger than a generic token; multiple hits reinforce confidence.
                score = sum(2 if normalize_product_name(keyword) == normalized else 1 for keyword in matched)
                scores.append((score, category, matched))

        if not scores:
            return {"category": "אחר", "confidence": 0.15, "source": "RULES", "reason": "לא נמצאה התאמה לחוקי הסיווג"}

        scores.sort(reverse=True)
        best_score, category, matched = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else 0
        margin = best_score - second_score
        confidence = min(0.99, 0.55 + best_score * 0.12 + margin * 0.08)
        return {"category": category, "confidence": round(confidence, 4), "source": "RULES", "reason": "מילות מפתח: " + ", ".join(matched[:5])}

    def record_feedback(self, tenant_id: int, user_id: int, product_id: int, product_name: str, actual_category: str, predicted_category=None, confidence=None):
        actual_category = (actual_category or "").strip()
        if actual_category not in CATEGORIES:
            raise BadRequest("Invalid product category")
        feedback = ProductClassificationFeedback(
            tenant_id=tenant_id,
            product_id=product_id,
            normalized_name=normalize_product_name(product_name),
            predicted_category=predicted_category,
            actual_category=actual_category,
            source="USER",
            confidence=confidence,
            created_by=user_id,
        )
        db.session.add(feedback)
        return feedback

    @staticmethod
    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, normalize_product_name(a), normalize_product_name(b)).ratio()
