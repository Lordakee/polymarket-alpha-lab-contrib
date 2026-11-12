# Redactions (FX-24 compliance, 2026-11-12)
Owner instruction forbids the server public address in any new file.
Byte-faithful mirror/snapshot artifacts were redacted post-extraction;
original bytes remain on the server. Pre-redaction sha256 below.

| file | original sha256 | redacted sha256 |
|---|---|---|
| ledger-snapshots/2026-11-12/VIEW-DIFF.md | a7f5cc36bf12737c305ca68250c498127f4f92d4337eaabc94b4c88f451fee1d | b1ed227f18a7ad4acc766ca3ad03cedec69b1a01af8942951608652648818697 |
| server-mirror/FX-04-wiring-proof.md | dce4f44a643b8c05dc34ea9241aff0a9237cf2f4fe30d7014a2707e91025f051 | 7e94943467676dc24d49d141e0253299719035163ea2fb98466350c1e211bc2c |
| server-mirror/MANIFEST-NOT-MIRRORED.md | d635c6fb374ac39875cc798c16e89c14d2d6a34a5a66808d03423df68b72f4a6 | 935db2c9c0c912eb315025962d9d792e19fdeb1660d3540e4693e59d4b40d9ef |
| server-mirror/MANIFEST.sha256 | edited-in-place-post-redaction (see note) | 1678ca089f2ebd6de724368d876ec58f5a22f5cf0aebe0b72aa41aab3efd85de |
| server-mirror/VERSION-CHECKIN.md | 93efb8a78d9a5db405a740117bb0b48d77ded27ec2ae0000b5685e7d9615d9a5 | 1a6caa94c89733fb9f2283927a7e9b39634ddc3003b21d8183575509f2780d34 |
| server-mirror/intl/wp_intl3/polymarket_alpha_lab/papersim/league_strength.py | d76b25e84b0b7f5a25f9b6a3af7fabde7efe66b5dd3a4f3b411dbd10bd2817a0 | 1733bbd90f6833c14d81d6223d408124c23a871c93065657a1a9a2786df30cd8 |
| server-mirror/round29/raw/write_scan.py | 93ed8a73524809356e0bdc2804aa3133b5bcf2bd62ab44cfd29e12183e2be9ff | 9d078a8cdcd753c5066c480aa2b35e491c90f0cb1cf1752780ab604d50517ab7 |
| server-mirror/round39/eredivisie_validate.py | 4f58c43b1c40e2e8c949b078eb9eeacbf6a9e7b6ffe3a705ea0c99ab1139a9b9 | 2d86775882a75f0f92471ef33bf9b6d5dc73bb2a970945ee9cae8edbcb78d39c |
| server-mirror/tools/fotmob_validate.py | 6e8be5cfa874047a97f3a926e65dca3a464392e2d07cc6dd803be8c04ed11cb0 | d0e049f3b24b316f268755ba08d03fcd055fb2daa3775b91aeb669dc8dd1fcb4 |


## Note (2026-11-12, review P2 fix)
MANIFEST.sha256 was edited after its post-redaction hash was first recorded
(redacted file-row hashes were updated in a second pass), so its redacted
sha256 above is the CURRENT final value recomputed at commit time; the
original-hash column entry is marked accordingly.
