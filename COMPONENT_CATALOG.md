# Toilet Map Component Catalog

## UI Components (`ui/`)

### `ui/components.py`
| Function | Description | Props |
|----------|-------------|-------|
| `build_toilet_card_html(t, rank, meta, compact)` | Build HTML for a single toilet card | ToiletDict, rank int, meta dict, compact bool |
| `render_toilet_card(t, rank, meta, compact)` | Render a Stremlit toilet card | Same as above |
| `render_score_legend()` | Show score gradient legend (💩→✨) | None |
| `build_result_context_text(...)` | Build result summary text | counts, pref, search, sort |
| `build_data_freshness_text(meta, t)` | Show data freshness info | meta, t |
| `_build_links_html(t)` | Build external links section | ToiletDict |
| `_build_confidence_note(confidence, count)` | Build confidence note for low-review items | float, int |

### `ui/sidebar.py`
| Function | Description | Props |
|----------|-------------|-------|
| `render_sidebar(t, prefectures, query_params)` | Render full sidebar UI | t dict, prefectures list, query_params dict |
| `get_translated_filters(lang)` | Get translated filter mappings | lang string |
| `_get_gps_via_component(attempt)` | Get GPS via component | attempt int |

### `ui/pagination.py`
| Function | Description | Props |
|----------|-------------|-------|
| `reset_page(filter_key)` | Reset page on filter change | filter_key string |
| `calc_pagination(total, page)` | Calculate pagination state | total int, page int |
| `render_pagination(total, page, total_pages, t)` | Render pagination UI | various |

### `ui/filters.py`
| Function | Description | Props |
|----------|-------------|-------|
| `filter_toilets(df, filter_types, ...)` | Apply filters with AND logic | DataFrame, list[str], ... |
| `search_toilets(df, query)` | Fuzzy search | DataFrame, query string |

### `ui/map_builder.py`
| Function | Description | Props |
|----------|-------------|-------|
| `build_map(toilets, lat, lng, zoom, tile)` | Build Folium map | list[ToiletDict], float, float, int, string |
| `calc_map_center(pref, meta, pref_stats)` | Calculate map center | string, dict, dict |

### `ui/data_loader.py`
| Function | Description | Props |
|----------|-------------|-------|
| `load_toilet_data(cache_token)` | Load data from SQLite with caching | optional tuple |
| `toilets_to_dataframe(toilets)` | Convert to DataFrame with equipment columns | list[ToiletDict] |
| `get_prefectures(df)` | Get prefecture list from DataFrame | DataFrame |

### `ui/popups.py`
| Function | Description | Props |
|----------|-------------|-------|
| `build_popup_html(t)` | Build marker popup HTML | ToiletDict |

## Batch Components (`batch/`)

| Module | Purpose |
|--------|---------|
| `process_data.py` | Raw JSON→canonical JSON processing |
| `to_sqlite.py` | JSON→SQLite cache population |
| `scoring.py` | Review scoring logic |
| `schema.py` | DB schema versioning |
| `models.py` | Pydantic data models |
| `verify_data.py` | Data integrity checks |
| `api_server.py` | FastAPI health & data API |
| `logging_config.py` | Centralized logging with JSON support |
