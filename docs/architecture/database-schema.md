# Database Schema

## Core Library: No Database

The core fapilog library requires **zero database setup**. It works immediately after `pip install fapilog`.

## Enterprise Plugin Databases

Individual plugins may include their own database requirements:

- **`fapilog-audit-trail`** - May include SQLite/PostgreSQL schemas
- **`fapilog-metrics-storage`** - May include time-series database schemas
- **`fapilog-compliance-tracker`** - May include compliance violation tracking

**Each plugin manages its own storage needs** - not the core library's responsibility.
