import { describe, expect, it } from "vitest";
import { buildHeaders, readCookie } from "./api";

describe("readCookie", () => {
  it("finds a cookie among several", () => {
    expect(readCookie("pf_csrf", "a=1; pf_csrf=abc%3D; b=2")).toBe("abc=");
  });
  it("returns null when missing", () => {
    expect(readCookie("pf_csrf", "a=1")).toBeNull();
  });
});

describe("buildHeaders", () => {
  it("echoes the CSRF cookie on state-changing requests", () => {
    expect(buildHeaders("POST", true, "pf_csrf=tok").get("X-CSRF-Token")).toBe("tok");
  });
  it("does not send it on reads", () => {
    expect(buildHeaders("GET", false, "pf_csrf=tok").get("X-CSRF-Token")).toBeNull();
  });
});
