import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * פונקציה המשלבת Class Names של Tailwind בצורה חכמה (מונעת התנגשויות)
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
