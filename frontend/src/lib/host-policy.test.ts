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

  it("recognizes expanded IPv6 loopback spellings via canonicalization", () => {
    expect(isLoopbackHostname("0:0:0:0:0:0:0:1")).toBe(true);
    expect(isLoopbackHostname("[0:0:0:0:0:0:0:1]")).toBe(true);
    expect(isLoopbackHostname(new URL("http://[0:0:0:0:0:0:0:1]/"))).toBe(true);
    expect(isLoopbackHostname("0:0:0:0:0:0:0:2")).toBe(false);
  });

  it("recognizes expanded IPv4-mapped IPv6 spellings via canonicalization", () => {
    expect(isIpv4MappedHostname("0:0:0:0:0:ffff:c0a8:101")).toBe(true);
    expect(isIpv4MappedHostname("::ffff:c0a8:0101")).toBe(true);
    expect(isIpv4MappedHostname("0:0:0:0:0:0:c0a8:101")).toBe(false);
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

  it("fails closed on legacy numeric encodings of private addresses", () => {
    for (const hostname of [
      // Leading-zero octets have octal semantics on legacy resolvers.
      "010.0.0.1",
      "0127.0.0.1",
      "0169.254.0.1",
      "0172.16.0.1",
      "0192.168.0.1",
      // Bare decimal/hex integers resolve as IP literals on some stacks.
      "2130706433",
      "0x7f000001",
      // Uncompressed private IPv6 spellings must canonicalize to private...
      "0:0:0:0:0:0:0:0",
      "0:0:0:0:0:0:0:1",
      "fc00:0000:0000:0000:0000:0000:0000:0001",
      "fe80:0:0:0:0:0:0:1",
      // ...and mapped literals with ambiguous dotted tails fail closed.
      "::ffff:010.0.0.001",
    ]) {
      expect(isPrivateOrLoopbackHostname(hostname), hostname).toBe(true);
    }
  });

  it("still classifies public canonical IPv6 spellings as non-private", () => {
    expect(isPrivateOrLoopbackHostname("2001:4860:4860:0:0:0:0:8888")).toBe(
      false,
    );
    expect(
      isPrivateOrLoopbackHostname(new URL("http://[2606:4700::6810:85e5]/")),
    ).toBe(false);
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
