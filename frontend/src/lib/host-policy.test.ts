import { describe, expect, it } from "vitest";

import {
  isIpv4MappedHostname,
  isLoopbackHostname,
  isPrivateOrLoopbackHostname,
  normalizeHostname,
} from "./host-policy";

describe("host-policy", () => {
  it("normalizes case, trailing root dots, and bracketed IPv6 in a stable order", () => {
    expect(normalizeHostname("EXAMPLE.COM...")).toBe("example.com");
    expect(normalizeHostname("[::1]")).toBe("::1");
    expect(normalizeHostname("[::1].")).toBe("::1");
    expect(normalizeHostname(new URL("http://[::1]/"))).toBe("::1");
  });

  it("recognizes only the supported exact loopback host forms", () => {
    expect(isLoopbackHostname("LOCALHOST.")).toBe(true);
    expect(isLoopbackHostname("127.0.0.1")).toBe(true);
    expect(isLoopbackHostname("[::1].")).toBe(true);
    expect(isLoopbackHostname("127.0.0.2")).toBe(false);
    expect(isLoopbackHostname("example.com")).toBe(false);
  });

  it("recognizes IPv4-mapped IPv6 syntax after normalization", () => {
    expect(isIpv4MappedHostname("[::ffff:192.168.1.1].")).toBe(true);
    expect(isIpv4MappedHostname("192.168.1.1")).toBe(false);
  });

  it("classifies private IPv4 and IPv6 ranges including mapped addresses", () => {
    for (const hostname of [
      "0.0.0.0",
      "10.0.0.1",
      "127.255.255.255",
      "169.254.1.1",
      "172.16.0.1",
      "172.31.255.255",
      "192.168.1.1",
      "::",
      "::1",
      "fc00::1",
      "fd00::1",
      "fe80::1",
      "::ffff:127.0.0.1",
      "::ffff:10.0.0.1",
      "::ffff:c0a8:0101",
    ]) {
      expect(isPrivateOrLoopbackHostname(hostname), hostname).toBe(true);
    }
  });

  it("does not classify public or malformed mapped addresses as private", () => {
    for (const hostname of [
      "8.8.8.8",
      "172.15.255.255",
      "172.32.0.0",
      "2001:4860:4860::8888",
      "::ffff:8.8.8.8",
      "::ffff:0808:0808",
      "::ffff:zzzz:1",
      "::ffff:7f00",
    ]) {
      expect(isPrivateOrLoopbackHostname(hostname), hostname).toBe(false);
    }
  });

  it("rejects SSRF-bypass hostnames that merely start with a private-IP prefix", () => {
    for (const hostname of [
      "10.0.0.1.attacker.com",
      "10.0.0.0.example.com",
      "10.255.255.255.malicious.org",
      "172.16.0.1.attacker.com",
      "172.31.255.255.evil.net",
      "192.168.1.1.attacker.com",
      "192.168.0.0.example.com",
      "127.0.0.1.attacker.com",
      "0.0.0.0.example.com",
      "169.254.0.1.attacker.com",
    ]) {
      expect(isPrivateOrLoopbackHostname(hostname), hostname).toBe(false);
    }
  });
});
