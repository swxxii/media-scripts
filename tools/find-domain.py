#!/usr/bin/env python3
"""
Find available domains where prefix + suffix (without the period) forms an English word.
For example: mu.ch = "much", bea.ch = "beach", rea.ch = "reach"
"""
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try:
    import whois
except ImportError:
    print("Error: python-whois package not found. Install with: pip install python-whois", file=sys.stderr)
    sys.exit(1)

try:
    import dns.resolver
except ImportError:
    print("Error: dnspython package not found. Install with: pip install dnspython", file=sys.stderr)
    sys.exit(1)

try:
    from english_words import get_english_words_set
except ImportError:
    print("Error: english-words package not found. Install with: pip install english-words", file=sys.stderr)
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Error: tqdm package not found. Install with: pip install tqdm", file=sys.stderr)
    sys.exit(1)

# Single cache of all domains confirmed registered, shared across all runs.
# Registration status doesn't depend on the suffix/length that surfaced a
# domain, so one list works regardless of arguments.
CACHE_FILE = Path(__file__).resolve().parent / ".find-domain.cache"
CACHE_MAX_AGE = 14 * 24 * 60 * 60  # 14 days, in seconds

def load_cache():
    """Load the set of known-registered domains from the cache file.

    The cache expires after CACHE_MAX_AGE; if the file is older it's wiped
    and treated as empty so stale registration data isn't trusted.
    """
    if not CACHE_FILE.exists():
        return set()
    try:
        if time.time() - CACHE_FILE.stat().st_mtime > CACHE_MAX_AGE:
            CACHE_FILE.unlink()
            print("Cache older than 14 days — wiped, rechecking all domains.", file=sys.stderr)
            return set()
        with open(CACHE_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    except Exception:
        return set()

def save_cache(registered_domains):
    """Save the set of known-registered domains to the cache file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            f.write('\n'.join(sorted(registered_domains)))
    except Exception:
        pass

def get_english_words_with_suffix(suffix, max_length):
    """Get English words that end with the given suffix, up to max_length, sorted by length"""
    words_set = get_english_words_set(['web2'], alpha=True, lower=True)
    words = [w for w in words_set if w.endswith(suffix) and len(w) - len(suffix) > 2 and len(w) <= max_length]
    words.sort(key=len)
    return words

def is_domain_available(domain):
    """Check domain availability via WHOIS, falling back to DNS SOA."""
    try:
        w = whois.whois(domain)
        if any([w.domain_name, w.registrar, w.creation_date]):
            return False
        # Inconclusive (unparsed TLD response) — fall through to DNS
    except whois.exceptions.WhoisDomainNotFoundError:
        return True  # WHOIS explicitly says not found
    except Exception:
        pass  # Fall through to DNS

    # DNS SOA fallback — SOA records exist only for registered domains
    try:
        dns.resolver.resolve(domain, 'SOA', tcp=False)
        return False
    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return True
    except Exception:
        return True

def run_tests():
    """Integration tests against known domains across the 20 most popular TLDs."""
    registered = [
        # domain          TLD
        "google.com",    # .com
        "cloudflare.net", # .net
        "mozilla.org",   # .org
        "spiegel.de",    # .de
        "amazon.fr",     # .fr
        "google.it",     # .it
        "google.pl",     # .pl
        "google.ca",     # .ca
        "google.es",     # .es
        "amazon.jp",     # .jp
        "github.io",     # .io
        "google.co",     # .co
        "google.nl",     # .nl
        "yandex.ru",     # .ru
        "google.uk",     # .uk
        "google.au",     # .au
        "amazon.in",     # .in
        "google.me",     # .me
        "google.tv",     # .tv
        "amazon.eu",     # .eu
    ]
    available = [
        "qxzjvwpbmfake.com",
        "zzznotrealdomain.net",
        "vwxqzunregistered.org",
    ]

    passed = failed = 0
    print("Running tests...\n")

    for domain in registered:
        result = is_domain_available(domain)
        ok = not result
        print(f"  {'PASS' if ok else 'FAIL'}  {domain}  (expected: registered, got: {'available' if result else 'registered'})")
        if ok: passed += 1
        else: failed += 1

    for domain in available:
        result = is_domain_available(domain)
        ok = result
        print(f"  {'PASS' if ok else 'FAIL'}  {domain}  (expected: available, got: {'available' if result else 'registered'})")
        if ok: passed += 1
        else: failed += 1

    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(0 if failed == 0 else 1)


def main():
    if '-t' in sys.argv or '--test' in sys.argv:
        run_tests()

    if len(sys.argv) < 3:
        print("Usage: python find-domain.py <suffixes> <max_length> [-v]", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  python find-domain.py net 10", file=sys.stderr)
        print("  python find-domain.py 'com,net,io' 10", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  -v, --verbose  Print all domain checks (including registered)", file=sys.stderr)
        print("  -t, --test     Run integration tests against known domains", file=sys.stderr)
        sys.exit(1)

    suffixes_arg = sys.argv[1]
    suffixes = [s.strip() for s in suffixes_arg.split(',')]

    try:
        max_length = int(sys.argv[2])
    except ValueError:
        print("Error: second argument must be an integer", file=sys.stderr)
        sys.exit(1)

    verbose = '-v' in sys.argv or '--verbose' in sys.argv

    # Load all known-registered domains so we can skip them this run.
    known_registered = load_cache()

    # Generate all domains for this run
    all_domains_for_suffixes = set()
    for suffix in suffixes:
        words = get_english_words_with_suffix(suffix, max_length)
        for word in words:
            prefix = word[:-len(suffix)]
            domain = prefix + '.' + suffix
            all_domains_for_suffixes.add(domain)

    # Skip domains we've already confirmed as registered
    domains_to_check = all_domains_for_suffixes - known_registered
    skipped = len(all_domains_for_suffixes) - len(domains_to_check)

    if not all_domains_for_suffixes:
        print(f"No English words found ending in '{suffixes_arg}' with max length {max_length}", file=sys.stderr)
        return

    if skipped:
        print(f"Skipping {skipped} cached registered domains\n", file=sys.stderr)

    if not domains_to_check:
        print("All domains already checked (cache expires after 14 days)", file=sys.stderr)
        return

    print(f"Found {len(all_domains_for_suffixes)} candidate domains, checking {len(domains_to_check)} (skipped {skipped} cached registered)...\n", file=sys.stderr)

    def check_domain_task(domain):
        is_available = is_domain_available(domain)

        if verbose:
            status = "AVAILABLE" if is_available else "registered"
            sys.stderr.write(f"{domain}: {status}\n")
            sys.stderr.flush()

        return domain if is_available else None

    # WHOIS servers rate-limit aggressively, keep concurrency low
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = executor.map(check_domain_task, domains_to_check)
        available_domains = [domain for domain in tqdm(results, total=len(domains_to_check), desc="Checking domains", unit="domain") if domain is not None]

    # Merge newly confirmed registered domains into the full cache, dropping
    # any that we just found to be available.
    available_set = set(available_domains)
    newly_registered = domains_to_check - available_set
    all_registered = (known_registered | newly_registered) - available_set

    print("\n" + "=" * 60, file=sys.stderr)
    print("Available domains (NOT registered):", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)

    for domain in sorted(available_domains, key=lambda d: (len(d), d)):
        print(domain)

    if not available_domains:
        print("(No available domains found)", file=sys.stderr)

    # Save registered domains to cache
    save_cache(all_registered)

if __name__ == '__main__':
    main()
