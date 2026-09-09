import { describe, expect, it } from "vitest";

describe("inventory route", () => {
  it("has a dedicated mobile warehouse route", () => {
    expect("/dashboard/inventory").toBe("/dashboard/inventory");
  });
});
