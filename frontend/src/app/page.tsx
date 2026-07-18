import { redirect } from "next/navigation";

// The app has no real landing page yet — AuthProvider handles the
// authenticated/unauthenticated split once inside /dashboard or /login.
export default function RootPage() {
  redirect("/dashboard");
}
