---
protocol: along
protocol_version: "4.5.1"
slug: along-storage-providers
type: feat
status: open
priority: medium
created: 2026-10-22
updated: 2026-10-22
agent: antigravity
tags: [storage, s3, sharepoint, telegram, infrastructure]
blocked_by: []
related: [feat--along-report-engine, feat--along-webdev-runner]
---

# Storage Provider Abstraction (Local, S3, SharePoint, Dispatch)

## Goal
Implement a pluggable storage abstraction layer for Along artifacts, reports, and visual verification assets. The subsystem manages uploading, addressing, and dispatching execution outputs to configured storage destinations (Local/Git fallback, AWS S3/MinIO/R2, SharePoint/M365, and notification channels like Telegram), keeping heavy binary assets from polluting the Git repository while maintaining full traceability from .along/ISSUES/.

## Problem Statement
Execution outputs (screenshots, DOM snapshots, network traces, visual verification reports) can easily bloat the Git history if stored directly as unmanaged binaries. However, development teams and corporate stakeholders require access in different destinations:
1. Technical developers need local fallback files placed right next to the active task in .along/artifacts/ or workspace.
2. Cloud/CI environments need object storage (AWS S3, MinIO, Cloudflare R2) with presigned or public URLs.
3. Enterprise non-technical stakeholders (management, QA, compliance) need direct access in corporate SharePoint/OneDrive document libraries.
4. Autonomous pipelines benefit from instant notifications and dispatch to channels like Telegram.

## Architecture & Interfaces

### 1. Unified Storage Interface (`scripts/alongkit/storage/`)
- Abstract base class `StorageProvider`:
  ```python
  class StorageProvider(ABC):
      @abstractmethod
      def upload(self, local_path: Path, destination_key: str, content_type: str = None) -> StorageRef:
          """Upload a local file and return an addressed StorageRef."""
          ...

      @abstractmethod
      def upload_bytes(self, data: bytes, destination_key: str, content_type: str = None) -> StorageRef:
          """Upload in-memory bytes directly."""
          ...
  ```
- `StorageRef` schema:
  - `url`: Direct, presigned, or local file link.
  - `key`: Normalized destination path/identifier.
  - `provider`: Identifier of the backing transport (`local`, `s3`, `sharepoint`, etc.).
  - `metadata`: Dictionary of provider-specific properties (e.g. SharePoint driveItemId, S3 ETag).

### 2. Supported Transports & Destinations
1. **Local Provider (`local`) [Default Fallback]**:
   - Stores assets in `.along/artifacts/<issue-slug>/` or a dedicated workspace directory.
   - Generates relative Markdown links for direct embedding inside `.along/ISSUES/<type>--<slug>.md` and session logs.
2. **S3 / Object Storage Provider (`s3`)**:
   - Compatible with AWS S3, MinIO, Cloudflare R2, and Ceph.
   - Configured via environment variables (`S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
   - Supports generating both public URLs and time-limited presigned URLs.
3. **SharePoint / Microsoft 365 Provider (`sharepoint`)**:
   - Connects to Microsoft Graph API (`/v1.0/sites/{site-id}/drives/{drive-id}/root:/...`).
   - Authenticates via Azure AD app registration (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`).
   - Uploads reports and folders to specified document libraries, returning corporate sharing links.
4. **Notification / Multi-Target Dispatch (`telegram` / `webhook`)**:
   - Allows broadcasting report summaries and screenshots directly to Telegram chats or webhooks when specified in issue configuration or CLI invocation.

### 3. Repository Configuration (`.along/config.yaml` / `.env`)
- Centralized configuration with environment override:
  ```yaml
  storage:
    default: local
    destinations:
      local:
        base_dir: .along/artifacts
      s3:
        bucket: my-team-along-artifacts
        endpoint: https://s3.eu-central-1.amazonaws.com
      sharepoint:
        site_name: ProductDelivery
        folder_path: /Shared Documents/AlongReports
  ```

### 4. CLI Interface
```bash
along storage upload <local-file> [--provider local|s3|sharepoint] [--destination-key <key>]
along storage test-connection [--provider <name>]
```

## Acceptance Criteria
- [ ] Base `StorageProvider` and `StorageRef` data models implemented in `scripts/alongkit/storage/`.
- [ ] `LocalStorageProvider` implemented as zero-dependency default fallback writing to `.along/artifacts/`.
- [ ] `S3StorageProvider` implemented with support for custom endpoints (MinIO/R2) and presigned URLs.
- [ ] `SharePointStorageProvider` implemented for Microsoft Graph API upload.
- [ ] Multi-destination dispatch support (e.g., upload to S3 and notify Telegram channel).
- [ ] Configuration parsing from `.along/config.yaml` and environment variables.
- [ ] CLI command `along storage` functional.
- [ ] Hermetic unit tests covering provider abstractions and error handling.
