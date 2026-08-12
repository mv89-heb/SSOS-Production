"""Automatic tenant-scoped product categorization.

The classifier is intentionally deterministic and dependency-free: it can run
for every imported product without an external AI provider. Human corrections
are learned and take precedence over rules; fuzzy matches are used only when
there is a strong previous human signal.
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

# Ordered keyword rules. More specific phrases appear before broad terms so
# e.g. "שניצל עוף" is not classified as generic "בשר".
RULES = {
    "מוצרי חלב": (
        "חלב", "גבינה", "גבינות", "קוטג", "יוגורט", "יוגורטים", "שמנת",
        "לבנה", "לבנה", "מעדן", "מעדנים", "חמאה", "אשל", "ריוויון", "ריוויון",
        "גבינת", "מוצר חלב", "מוצרי חלב",
    ),
    "ירקות": (
        "עגבניה", "עגבניות", "מלפפון", "מלפפונים", "גזר", "גזרים", "בצל",
        "בצלים", "תפוח אדמה", "תפוחי אדמה", "תפו אדמה", "פלפל", "פלפלים",
        "כרוב", "כרובים", "חסה", "קישוא", "קישואים", "ברוקולי", "כרובית",
        "סלק", "צנונית", "בטטה", "בטטות", "חציל", "חצילים", "ירק", "ירקות",
    ),
    "פירות": (
        "תפוח", "תפוחים", "בננה", "בננות", "תפוז", "תפוזים", "קלמנטינה",
        "קלמנטינות", "אגס", "אגסים", "ענבים", "אבטיח", "מלון", "אפרסק",
        "אפרסקים", "שזיף", "שזיפים", "מנגו", "קיווי", "אננס", "פרי", "פירות",
    ),
    "עוף": (
        "שניצל עוף", "חזה עוף", "כרעיים", "כנפיים", "פרגית", "פרגיות",
        "עוף", "עופות", "נאגטס עוף", "פסטרמה עוף",
    ),
    "בשר": (
        "בשר", "בשרים", "אסאדו", "צלי", "סטייק", "סינטה", "אנטריקוט",
        "המבורגר", "קבב", "קבבים", "קציצה", "קציצות", "בשר טחון", "טחון בקר",
    ),
    "דגים": (
        "דג", "דגים", "טונה", "סלמון", "אמנון", "מושט", "קרפיון", "סרדין",
        "סרדינים", "פילה דג", "פילה סלמון",
    ),
    "קפואים": (
        "קפוא", "קפואים", "קפואות", "קפוא", "צ'יפס קפוא", "ציפס קפוא",
        "בורקס קפוא", "בורקסים קפואים", "טבעות בצל", "אפונה קפואה",
        "שעועית קפואה", "ירקות קפואים", "פירות קפואים", "שניצל קפוא",
    ),
    "שימורים": (
        "שימורים", "שימור", "תירס בקופסה", "תירס משומר", "זיתים", "זית",
        "חמוצים", "חמוץ", "שעועית שימורים", "קופסת שימורים", "קופסאות שימורים",
        "טונה בשימורים",
    ),
    "מזון יבש": (
        "אורז", "אורזים", "פסטה", "ספגטי", "קוסקוס", "קמח", "סוכר", "קטניות",
        "עדשים", "בורגול", "פתיתים", "גריסים", "שיבולת שועל", "קורנפלקס",
        "דגני בוקר", "מזון יבש", "יבשים",
    ),
    "מאפים ולחמים": (
        "לחם", "לחמים", "לחמניה", "לחמניות", "פיתה", "פיתות", "בגט", "בגטים",
        "עוגה", "עוגות", "מאפה", "מאפים", "קרואסון", "קרואסונים", "חלה", "חלות",
    ),
    "משקאות": (
        "מים", "מים מינרליים", "מיץ", "מיצים", "סודה", "קולה", "שתיה", "שתייה",
        "משקה", "משקאות", "קפה", "קפה נמס", "תה", "שוקו", "מיץ תפוזים",
    ),
    "חטיפים": (
        "במבה", "ביסלי", "חטיף", "חטיפים", "צ'יפס חטיף", "קרקרים", "קרקר",
        "בייגלה", "פופקורן",
    ),
    "ממתקים": (
        "שוקולד", "שוקולדים", "סוכריה", "סוכריות", "ממתק", "ממתקים", "וופל",
        "וופלים", "מרשמלו", "גומי", "סוכריות גומי", "טופי",
    ),
    "רטבים ותבלינים": (
        "קטשופ", "מיונז", "חרדל", "רוטב", "רטבים", "תבלין", "תבלינים", "מלח",
        "פלפל שחור", "פפריקה", "כמון", "כורכום", "שום כתוש", "רוטב סויה",
        "טחינה", "חומוס",
    ),
    "חד פעמי": (
        "חד פעמי", "חדפ", "כוסות חד", "צלחות חד", "סכו", "סכום חד", "מפיות",
        "קשיות", "מזלגות חד", "כפיות חד", "צלחות", "כוסות חד פעמיות",
    ),
    "ניקיון": (
        "אקונומיקה", "נוזל כלים", "אבקת כביסה", "מרכך", "ניקוי", "ניקיון", "סבון",
        "סבון כלים", "שקיות אשפה", "שקית אשפה", "מטליות", "נייר ניקוי", "מסיר שומנים",
    ),
    "ציוד מטבח": (
        "סיר", "מחבת", "סכין", "קרש חיתוך", "כלי מטבח", "תבנית", "קערה",
        "קערות", "מלקחיים", "פותחן", "כף הגשה", "ציוד מטבח",
    ),
}


def normalize_product_name(name: str) -> str:
    value = (name or "").strip().casefold()
    # Normalize common Hebrew/typographic variants before matching.
    value = value.replace("״", '"').replace("׳", "'")
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:ק\"ג|קג|גרם|גר'|ליטר|ל'|מ\"ל|מל|יח')\b", " ", value)
    value = re.sub(r"[^א-תa-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


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
        # Feedback volume is intentionally bounded. Exact matches are handled
        # separately; this scan only supports strong fuzzy reuse of human
        # decisions and avoids an unbounded table scan.
        recent = (
            db.session.query(ProductClassificationFeedback)
            .filter_by(tenant_id=tenant_id)
            .order_by(ProductClassificationFeedback.created_at.desc(), ProductClassificationFeedback.id.desc())
            .limit(1000)
            .all()
        )
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
            return {
                "category": feedback.actual_category,
                "confidence": 1.0,
                "source": "LEARNED",
                "reason": "התאמה להחלטה קודמת של משתמש",
            }

        similar_feedback, similarity = self._similar_feedback(tenant_id, normalized)
        if similar_feedback is not None and similarity >= 0.93:
            return {
                "category": similar_feedback.actual_category,
                "confidence": round(min(0.99, similarity), 4),
                "source": "LEARNED",
                "reason": f"התאמה למוצר שסווג בעבר ({similarity:.0%})",
            }

        scores = []
        for category, keywords in RULES.items():
            matched = []
            score = 0.0
            for keyword in keywords:
                normalized_keyword = normalize_product_name(keyword)
                if not normalized_keyword:
                    continue
                if normalized_keyword == normalized:
                    matched.append(keyword)
                    score += 4.0
                elif normalized_keyword in normalized:
                    matched.append(keyword)
                    # Longer phrases are stronger evidence than short words.
                    score += 1.0 + min(1.5, len(normalized_keyword.split()) * 0.5)
                else:
                    # Token overlap catches plural/compound Hebrew names that
                    # contain the useful words in a different order.
                    name_tokens = set(normalized.split())
                    keyword_tokens = set(normalized_keyword.split())
                    overlap = len(name_tokens & keyword_tokens)
                    if overlap:
                        matched.append(keyword)
                        score += 0.6 * overlap
            if matched:
                scores.append((score, category, matched))

        if not scores:
            return {
                "category": "אחר",
                "confidence": 0.15,
                "source": "RULES",
                "reason": "לא נמצאה התאמה לחוקי הסיווג; ניתן לתקן ידנית והמערכת תלמד את ההחלטה",
            }

        scores.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, category, matched = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else 0.0
        margin = max(0.0, best_score - second_score)
        confidence = min(0.99, 0.50 + min(best_score, 5.0) * 0.08 + min(margin, 3.0) * 0.08)
        return {
            "category": category,
            "confidence": round(confidence, 4),
            "source": "RULES",
            "reason": "מילות מפתח: " + ", ".join(matched[:5]),
        }

    def record_feedback(
        self,
        tenant_id: int,
        user_id: int,
        product_id: int,
        product_name: str,
        actual_category: str,
        predicted_category=None,
        confidence=None,
    ):
        actual_category = (actual_category or "").strip()
        normalized_name = normalize_product_name(product_name)
        if actual_category not in CATEGORIES:
            raise BadRequest("Invalid product category")
        if not normalized_name:
            raise BadRequest("Product name is required for classification")

        feedback = ProductClassificationFeedback(
            tenant_id=tenant_id,
            product_id=product_id,
            normalized_name=normalized_name,
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
