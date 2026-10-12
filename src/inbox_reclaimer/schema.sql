-- Journal migration 1. Mutation evidence tables exist, but Gate A forbids writes to them.
CREATE TABLE accounts (
 account_id TEXT PRIMARY KEY, gmail_identity TEXT NOT NULL, oauth_client_id TEXT NOT NULL,
 identity_subject TEXT, UNIQUE(gmail_identity, oauth_client_id));
CREATE TABLE plans (
 account_id TEXT NOT NULL REFERENCES accounts(account_id), plan_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0),
 action TEXT NOT NULL CHECK(action IN ('trash','permanent_delete','restore')),
 policy_version TEXT NOT NULL, inventory_generation TEXT NOT NULL, created_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('draft','sealed','superseded','closed')),
 PRIMARY KEY(account_id,plan_id,revision));
CREATE TABLE batches (
 account_id TEXT NOT NULL, plan_id TEXT NOT NULL, revision INTEGER NOT NULL, batch_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('SENDER_NEWSLETTER','SIZE_AGE','CATEGORY_AGE','PURGE_CONFIRMED_TRASH','RESTORE')),
 membership_digest TEXT NOT NULL, message_count INTEGER NOT NULL CHECK(message_count>0),
 estimated_bytes INTEGER NOT NULL CHECK(estimated_bytes>=0),
 PRIMARY KEY(account_id,plan_id,revision,batch_id),
 FOREIGN KEY(account_id,plan_id,revision) REFERENCES plans(account_id,plan_id,revision));
CREATE TABLE batch_members (
 account_id TEXT NOT NULL, plan_id TEXT NOT NULL, revision INTEGER NOT NULL, batch_id TEXT NOT NULL,
 message_id TEXT NOT NULL, source_operation_id TEXT, reasons_json TEXT NOT NULL DEFAULT '[]',
 PRIMARY KEY(account_id,plan_id,revision,message_id),
 FOREIGN KEY(account_id,plan_id,revision,batch_id) REFERENCES batches(account_id,plan_id,revision,batch_id));
CREATE INDEX batch_listing ON batch_members(account_id,plan_id,revision,batch_id,message_id);
CREATE TABLE batch_rejections (
 account_id TEXT NOT NULL, plan_id TEXT NOT NULL, revision INTEGER NOT NULL, batch_id TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(account_id,plan_id,revision,batch_id),
 FOREIGN KEY(account_id,plan_id,revision,batch_id) REFERENCES batches(account_id,plan_id,revision,batch_id));
CREATE TABLE approvals (
 account_id TEXT NOT NULL, approval_id TEXT NOT NULL, plan_id TEXT NOT NULL, revision INTEGER NOT NULL,
 batch_id TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('trash','permanent_delete','restore')),
 membership_digest TEXT NOT NULL, policy_version TEXT NOT NULL, principal_id TEXT NOT NULL,
 source_event_id TEXT NOT NULL, challenge_id TEXT NOT NULL UNIQUE,
 decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')), issued_at TEXT NOT NULL,
 expires_at TEXT NOT NULL, revoked_at TEXT, evidence_json TEXT NOT NULL,
 PRIMARY KEY(account_id,approval_id), UNIQUE(account_id,source_event_id),
 FOREIGN KEY(account_id,plan_id,revision,batch_id) REFERENCES batches(account_id,plan_id,revision,batch_id));
CREATE TABLE operations (
 account_id TEXT NOT NULL, operation_id TEXT NOT NULL, approval_id TEXT NOT NULL, message_id TEXT NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('trash','permanent_delete','restore')), step TEXT NOT NULL,
 attempt INTEGER NOT NULL, source_operation_id TEXT, dry_run INTEGER NOT NULL CHECK(dry_run IN (0,1)),
 state TEXT NOT NULL CHECK(state IN ('pending','confirmed','unknown','failed','skipped')),
 reason TEXT, attribution TEXT, preimage_json TEXT NOT NULL, postimage_json TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(account_id,operation_id),
 UNIQUE(account_id,approval_id,message_id,step,attempt,dry_run),
 FOREIGN KEY(account_id,approval_id) REFERENCES approvals(account_id,approval_id),
 FOREIGN KEY(account_id,source_operation_id) REFERENCES operations(account_id,operation_id));
CREATE INDEX operations_recovery ON operations(account_id,state);
CREATE INDEX operations_provenance ON operations(account_id,message_id,action,dry_run);
CREATE INDEX approval_scope ON approvals(account_id,plan_id,revision,action);
CREATE TABLE journal_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL REFERENCES accounts(account_id),
 operation_id TEXT, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(account_id,operation_id) REFERENCES operations(account_id,operation_id));
CREATE TABLE export_cursors (export_name TEXT PRIMARY KEY,last_event_id INTEGER NOT NULL);
CREATE TABLE sender_protections (
 account_id TEXT NOT NULL REFERENCES accounts(account_id), sender_address TEXT NOT NULL,
 reason TEXT, created_at TEXT NOT NULL, PRIMARY KEY(account_id,sender_address));
CREATE TRIGGER account_singleton BEFORE INSERT ON accounts WHEN EXISTS(SELECT 1 FROM accounts)
 BEGIN SELECT RAISE(ABORT,'single-account journal'); END;
CREATE TRIGGER account_immutable_update BEFORE UPDATE ON accounts
 BEGIN SELECT RAISE(ABORT,'account immutable'); END;
CREATE TRIGGER account_immutable_delete BEFORE DELETE ON accounts
 BEGIN SELECT RAISE(ABORT,'account immutable'); END;
CREATE TRIGGER sealed_plan_update BEFORE UPDATE ON plans WHEN OLD.status!='draft'
 BEGIN SELECT RAISE(ABORT,'sealed plan immutable'); END;
CREATE TRIGGER sealed_plan_delete BEFORE DELETE ON plans WHEN OLD.status!='draft'
 BEGIN SELECT RAISE(ABORT,'sealed plan immutable'); END;
CREATE TRIGGER no_approvals_gate_a BEFORE INSERT ON approvals
 BEGIN SELECT RAISE(ABORT,'Gate A cannot mint approvals'); END;
CREATE TRIGGER no_operations_gate_a BEFORE INSERT ON operations
 BEGIN SELECT RAISE(ABORT,'Gate A cannot create operations'); END;
CREATE TRIGGER audit_no_update BEFORE UPDATE ON journal_events
 BEGIN SELECT RAISE(ABORT,'audit append only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON journal_events
 BEGIN SELECT RAISE(ABORT,'audit append only'); END;
CREATE TRIGGER rejection_no_update BEFORE UPDATE ON batch_rejections
 BEGIN SELECT RAISE(ABORT,'rejection immutable'); END;
CREATE TRIGGER rejection_no_delete BEFORE DELETE ON batch_rejections
 BEGIN SELECT RAISE(ABORT,'rejection immutable'); END;
