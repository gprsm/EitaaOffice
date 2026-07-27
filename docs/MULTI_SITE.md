# Multiple WordPress sites

Bridge supports multiple independently configured WordPress destinations.

- `default_site_key` is used only when no site is explicitly selected.
- Every command targets exactly one site.
- There is no automatic fan-out or broadcast to all sites.
- Credentials, default category, TLS policy, timeout, and safe GET retry count are scoped per site.
- Core publication deduplication uses `target_type="wordpress"` and `target_key=<site_key>`.

List destinations safely:

```bat
run_sites_list.bat
```

Select destinations explicitly:

```bat
run_wp_test.bat medical-site
run_wp_info.bat journal-site
run_publication_preview.bat journal-site "selected_channel.json" 5370
run_publication_one.bat journal-site "selected_channel.json" 5370
```

The same Eitaa message may be published once to each configured `site_key`. Changing a `site_key` later represents a different publication destination, so destination keys should remain stable.
