import createMiddleware from "next-intl/middleware";
import { routing } from "./src/i18n/routing";

export default createMiddleware(routing);

export const config = {
  // החלת המידלוור על כל הנתיבים למעט קבצי עיצוב, תמונות, נתיבי מערכת ופניות API
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
