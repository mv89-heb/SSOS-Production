import { defineRouting } from "next-intl/routing";
import { createNavigation } from "next-intl/navigation";

export const routing = defineRouting({
  locales: ["he", "en"],
  defaultLocale: "he",
  localePrefix: "always", // מבטיח שכל נתיב יקבל תמיד קידומת /he או /en
});

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
