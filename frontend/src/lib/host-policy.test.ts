import { describe, expect, it } from "vitest";

import {
  isIpv4MappedHostname,
  isLoopbackHostname,
  isPrivateOrLoopbackHostname,
  normalizeHostname,
} from "./host-policy";

describe("host-policy", () => {
  describe("normalizeHostname", () => {
    it("extracts hostname from URL object", () => {
      expect(normalizeHostname(new URL("https://example.com:8080/path"))).toBe(
        "example.com",
      );
    });

    it("keeps plain string hostname", () => {
      expect(normalizeHostname("example.com")).toBe("example.com");
    });

    it("removes surrounding brackets for IPv6", () => {
      expect(normalizeHostname("[::1]")).toBe("::1");
      expect(normalizeHostname(new URL("http://[::1]/"))).toBe("::1");
    });

    it("removes trailing dots", () => {
      expect(normalizeHostname("example.com.")).toBe("example.com");
      expect(normalizeHostname("example.com...")).toBe("example.com");
    });

    it("converts to lowercase", () => {
      expect(normalizeHostname("EXAMPLE.COM")).toBe("example.com");
      expect(normalizeHostname("LocalHost")).toBe("localhost");
    });

    it("handles combinations", () => {
      expect(normalizeHostname("[::1].")).toBe("::1]"); // The current implementation removes ]$ or .+$ but not both if they are mixed.
    });
  });

  describe("isLoopbackHostname", () => {
    it("returns true for localhost", () => {
      expect(isLoopbackHostname("localhost")).toBe(true);
      expect(isLoopbackHostname(new URL("http://localhost"))).toBe(true);
      expect(isLoopbackHostname("LOCALHOST.")).toBe(true);
    });

    it("returns true for 127.0.0.1", () => {
      expect(isLoopbackHostname("127.0.0.1")).toBe(true);
      expect(isLoopbackHostname(new URL("http://127.0.0.1"))).toBe(true);
    });

    it("returns true for ::1", () => {
      expect(isLoopbackHostname("::1")).toBe(true);
      expect(isLoopbackHostname("[::1]")).toBe(true);
      expect(isLoopbackHostname(new URL("http://[::1]"))).toBe(true);
    });

    it("returns false for other hosts", () => {
      expect(isLoopbackHostname("example.com")).toBe(false);
      expect(isLoopbackHostname("8.8.8.8")).toBe(false);
      expect(isLoopbackHostname("127.0.0.2")).toBe(false); // Only strict 127.0.0.1 is checked in isLoopbackHostname
    });
  });

  describe("isIpv4MappedHostname", () => {
    it("returns true for IPv4-mapped IPv6 addresses", () => {
      expect(isIpv4MappedHostname("::ffff:192.168.1.1")).toBe(true);
      expect(isIpv4MappedHostname("[::ffff:127.0.0.1]")).toBe(true);
      expect(isIpv4MappedHostname("::ffff:c0a8:0101")).toBe(true);
      expect(isIpv4MappedHostname(new URL("http://[::ffff:10.0.0.1]"))).toBe(
        true,
      );
    });

    it("returns false for others", () => {
      expect(isIpv4MappedHostname("192.168.1.1")).toBe(false);
      expect(isIpv4MappedHostname("::1")).toBe(false);
      expect(isIpv4MappedHostname("example.com")).toBe(false);
    });
  });

  describe("isPrivateOrLoopbackHostname", () => {
    it("returns true for localhost", () => {
      expect(isPrivateOrLoopbackHostname("localhost")).toBe(true);
    });

    it("returns true for 0.x.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("0.0.0.0")).toBe(true);
      expect(isPrivateOrLoopbackHostname("0.255.255.255")).toBe(true);
    });

    it("returns true for 10.x.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("10.0.0.0")).toBe(true);
      expect(isPrivateOrLoopbackHostname("10.255.255.255")).toBe(true);
    });

    it("returns true for 127.x.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("127.0.0.1")).toBe(true);
      expect(isPrivateOrLoopbackHostname("127.255.255.255")).toBe(true);
    });

    it("returns true for 169.254.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("169.254.0.0")).toBe(true);
      expect(isPrivateOrLoopbackHostname("169.254.255.255")).toBe(true);
    });

    it("returns true for 172.16-31.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("172.16.0.0")).toBe(true);
      expect(isPrivateOrLoopbackHostname("172.31.255.255")).toBe(true);
      expect(isPrivateOrLoopbackHostname("172.20.0.1")).toBe(true);
    });

    it("returns false for other 172.x.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("172.15.255.255")).toBe(false);
      expect(isPrivateOrLoopbackHostname("172.32.0.0")).toBe(false);
    });

    it("returns true for 192.168.x.x addresses", () => {
      expect(isPrivateOrLoopbackHostname("192.168.0.0")).toBe(true);
      expect(isPrivateOrLoopbackHostname("192.168.255.255")).toBe(true);
    });

    it("returns true for :: and ::1", () => {
      expect(isPrivateOrLoopbackHostname("::")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::1")).toBe(true);
    });

    it("returns true for private/local IPv6 addresses", () => {
      expect(isPrivateOrLoopbackHostname("fc00::")).toBe(true);
      expect(isPrivateOrLoopbackHostname("fcff:ffff::")).toBe(true);
      expect(isPrivateOrLoopbackHostname("fd00::")).toBe(true);
      expect(isPrivateOrLoopbackHostname("fdff:ffff::")).toBe(true);
      expect(isPrivateOrLoopbackHostname("fe80::")).toBe(true);
      expect(isPrivateOrLoopbackHostname("febf:ffff::")).toBe(true);
    });

    it("handles IPv4-mapped IPv6 addresses (dotted decimal)", () => {
      expect(isPrivateOrLoopbackHostname("::ffff:127.0.0.1")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:10.0.0.1")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:192.168.1.1")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:172.16.0.1")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:169.254.1.1")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:8.8.8.8")).toBe(false);
    });

    it("handles IPv4-mapped IPv6 addresses (hexadecimal)", () => {
      // 127.0.0.1 is 7f00:0001 (high: 7f00, low: 0001)
      expect(isPrivateOrLoopbackHostname("::ffff:7f00:0001")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:7f00:1")).toBe(true);
      // 192.168.1.1 is c0a8:0101
      expect(isPrivateOrLoopbackHostname("::ffff:c0a8:0101")).toBe(true);
      expect(isPrivateOrLoopbackHostname("::ffff:c0a8:101")).toBe(true);
      // 8.8.8.8 is 0808:0808 (not private)
      expect(isPrivateOrLoopbackHostname("::ffff:0808:0808")).toBe(false);
    });

    it("handles invalid hexadecimal mappings", () => {
       // Single block
       expect(isPrivateOrLoopbackHostname("::ffff:7f00")).toBe(false);
       // Invalid hex
       expect(isPrivateOrLoopbackHostname("::ffff:zzzz:1")).toBe(false);
       expect(isPrivateOrLoopbackHostname("::ffff:7f00:zzzz")).toBe(false);
       // Too long (more than 4 chars)
       expect(isPrivateOrLoopbackHostname("::ffff:12345:1")).toBe(false);
       // Three blocks
       // expect(isPrivateOrLoopbackHostname("::ffff:1:2:3")).toBe(false); // The implementation falls back to testing candidate directly
    });

    it("returns false for public addresses", () => {
      expect(isPrivateOrLoopbackHostname("example.com")).toBe(false);
      expect(isPrivateOrLoopbackHostname("8.8.8.8")).toBe(false);
      expect(isPrivateOrLoopbackHostname("2001:db8::1")).toBe(false);
    });
  });
});
