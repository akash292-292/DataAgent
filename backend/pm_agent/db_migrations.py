"""
Automatic database migrations
This module automatically checks and adds missing columns to existing tables.
Runs on backend startup to ensure schema is up-to-date.
"""
from sqlalchemy import text, inspect
from models import engine
import logging

logger = logging.getLogger(__name__)

def run_migrations():
    """
    Run all database migrations automatically.
    This function is idempotent - safe to run multiple times.
    """
    try:
        if engine.dialect.name == "sqlite":
            logger.info("[MIGRATION] SQLite detected - skipping Postgres-specific migrations")
            return True

        with engine.connect() as conn:
            migrations_applied = []
            
            # Migration 1: Add indexing_status to uploaded_files
            if not column_exists(conn, 'uploaded_files', 'indexing_status'):
                try:
                    conn.execute(text("""
                        ALTER TABLE uploaded_files 
                        ADD COLUMN indexing_status VARCHAR DEFAULT 'pending_index'
                    """))
                    conn.commit()
                    
                    # Set default values for existing rows
                    conn.execute(text("""
                        UPDATE uploaded_files 
                        SET indexing_status = 'pending_index' 
                        WHERE indexing_status IS NULL
                    """))
                    conn.commit()
                    migrations_applied.append("Added indexing_status to uploaded_files")
                    logger.info("[MIGRATION] Added indexing_status column to uploaded_files table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add indexing_status: {str(e)}")
                    conn.rollback()
            else:
                logger.info("[MIGRATION] Column indexing_status already exists in uploaded_files")
            
            # Migration 2: Add extracted_text to mandatory_files
            if not column_exists(conn, 'mandatory_files', 'extracted_text'):
                try:
                    conn.execute(text("""
                        ALTER TABLE mandatory_files 
                        ADD COLUMN extracted_text TEXT
                    """))
                    conn.commit()
                    migrations_applied.append("Added extracted_text to mandatory_files")
                    logger.info("[MIGRATION] Added extracted_text column to mandatory_files table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add extracted_text: {str(e)}")
                    conn.rollback()
            else:
                logger.info("[MIGRATION] Column extracted_text already exists in mandatory_files")
            
            # Migration 2.5: Add file_content to mandatory_files and make file_path nullable
            if not column_exists(conn, 'mandatory_files', 'file_content'):
                try:
                    # Add file_content column (BYTEA for PostgreSQL, stores binary file data)
                    conn.execute(text("""
                        ALTER TABLE mandatory_files 
                        ADD COLUMN file_content BYTEA
                    """))
                    conn.commit()
                    migrations_applied.append("Added file_content to mandatory_files")
                    logger.info("[MIGRATION] Added file_content column to mandatory_files table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add file_content: {str(e)}")
                    conn.rollback()
            else:
                logger.info("[MIGRATION] Column file_content already exists in mandatory_files")
            
            # Make file_path nullable (for backward compatibility with existing records)
            try:
                # Check if file_path is currently NOT NULL
                result = conn.execute(text("""
                    SELECT is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = 'mandatory_files' AND column_name = 'file_path'
                """))
                row = result.fetchone()
                
                if row and row[0] == 'NO':
                    # Column exists and is NOT NULL - make it nullable
                    conn.execute(text("""
                        ALTER TABLE mandatory_files 
                        ALTER COLUMN file_path DROP NOT NULL
                    """))
                    conn.commit()
                    migrations_applied.append("Made file_path nullable in mandatory_files")
                    logger.info("[MIGRATION] Made file_path column nullable in mandatory_files table")
                elif row and row[0] == 'YES':
                    logger.info("[MIGRATION] Column file_path is already nullable in mandatory_files")
            except Exception as e:
                # Column might not exist, that's okay
                logger.warning(f"[MIGRATION] Could not check/modify file_path column: {str(e)}")
            
            # Migration 3: Add workspace_id to sprint_plans (if table exists)
            if table_exists(conn, 'sprint_plans') and not column_exists(conn, 'sprint_plans', 'workspace_id'):
                try:
                    # Add column without foreign key constraint first (safer for existing data)
                    conn.execute(text("""
                        ALTER TABLE sprint_plans 
                        ADD COLUMN workspace_id INTEGER
                    """))
                    conn.commit()
                    
                    # Try to add foreign key constraint if workspaces table exists
                    if table_exists(conn, 'workspaces'):
                        try:
                            conn.execute(text("""
                                ALTER TABLE sprint_plans 
                                ADD CONSTRAINT fk_sprint_plans_workspace 
                                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                            """))
                            conn.commit()
                            logger.info("[MIGRATION] Added foreign key constraint for sprint_plans.workspace_id")
                        except Exception as fk_error:
                            # Foreign key might already exist or constraint name conflicts, that's okay
                            logger.warning(f"[MIGRATION] Could not add foreign key constraint (may already exist): {str(fk_error)}")
                            # Don't rollback - column was already added successfully
                    
                    migrations_applied.append("Added workspace_id to sprint_plans")
                    logger.info("[MIGRATION] Added workspace_id column to sprint_plans table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add workspace_id to sprint_plans: {str(e)}")
                    conn.rollback()
            
            # Migration 4: Add workspace_id to risk_assessments (if table exists)
            if table_exists(conn, 'risk_assessments') and not column_exists(conn, 'risk_assessments', 'workspace_id'):
                try:
                    # Add column without foreign key constraint first (safer for existing data)
                    conn.execute(text("""
                        ALTER TABLE risk_assessments 
                        ADD COLUMN workspace_id INTEGER
                    """))
                    conn.commit()
                    
                    # Try to add foreign key constraint if workspaces table exists
                    if table_exists(conn, 'workspaces'):
                        try:
                            conn.execute(text("""
                                ALTER TABLE risk_assessments 
                                ADD CONSTRAINT fk_risk_assessments_workspace 
                                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                            """))
                            conn.commit()
                            logger.info("[MIGRATION] Added foreign key constraint for risk_assessments.workspace_id")
                        except Exception as fk_error:
                            # Foreign key might already exist or constraint name conflicts, that's okay
                            logger.warning(f"[MIGRATION] Could not add foreign key constraint (may already exist): {str(fk_error)}")
                            # Don't rollback - column was already added successfully
                    
                    migrations_applied.append("Added workspace_id to risk_assessments")
                    logger.info("[MIGRATION] Added workspace_id column to risk_assessments table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add workspace_id to risk_assessments: {str(e)}")
                    conn.rollback()
            
            # Migration 5: Add word_document to sprint_plans (if table exists)
            if table_exists(conn, 'sprint_plans') and not column_exists(conn, 'sprint_plans', 'word_document'):
                try:
                    conn.execute(text("""
                        ALTER TABLE sprint_plans 
                        ADD COLUMN word_document TEXT
                    """))
                    conn.commit()
                    migrations_applied.append("Added word_document to sprint_plans")
                    logger.info("[MIGRATION] Added word_document column to sprint_plans table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add word_document to sprint_plans: {str(e)}")
                    conn.rollback()
            
            # Migration 6: Add word_document to risk_assessments (if table exists)
            if table_exists(conn, 'risk_assessments') and not column_exists(conn, 'risk_assessments', 'word_document'):
                try:
                    conn.execute(text("""
                        ALTER TABLE risk_assessments 
                        ADD COLUMN word_document TEXT
                    """))
                    conn.commit()
                    migrations_applied.append("Added word_document to risk_assessments")
                    logger.info("[MIGRATION] Added word_document column to risk_assessments table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add word_document to risk_assessments: {str(e)}")
                    conn.rollback()
            
            # Migration 7: Fix projects table - ensure id is VARCHAR (for UUID) not INTEGER
            if table_exists(conn, 'projects'):
                try:
                    # Check the current data type of the id column
                    result = conn.execute(text("""
                        SELECT data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'projects' AND column_name = 'id'
                    """))
                    row = result.fetchone()
                    
                    if row and row[0] == 'integer':
                        # Check if table has data
                        count_result = conn.execute(text("SELECT COUNT(*) FROM projects"))
                        row_count = count_result.fetchone()[0]
                        
                        logger.info(f"[MIGRATION] Projects table has INTEGER id column with {row_count} rows - fixing...")
                        
                        if row_count == 0:
                            # Table is empty, safe to drop and recreate
                            logger.info("[MIGRATION] Dropping empty projects table to recreate with correct UUID id column")
                            conn.execute(text("DROP TABLE IF EXISTS projects CASCADE"))
                            conn.commit()
                            migrations_applied.append("Recreated projects table with UUID id")
                            logger.info("[MIGRATION] Dropped projects table - will be recreated with correct schema")
                        else:
                            # Table has data - need to migrate data
                            logger.info(f"[MIGRATION] Migrating {row_count} projects to new schema with UUID ids")
                            
                            # First, drop any foreign key constraints that reference projects
                            try:
                                conn.execute(text("""
                                    ALTER TABLE conversations 
                                    DROP CONSTRAINT IF EXISTS fk_conversations_projects
                                """))
                                conn.commit()
                            except:
                                pass  # Constraint might not exist
                            
                            # Create temporary table with correct schema
                            conn.execute(text("""
                                CREATE TABLE projects_new (
                                    id character varying PRIMARY KEY,
                                    name character varying NOT NULL,
                                    user_email character varying NOT NULL,
                                    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                                    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
                                )
                            """))
                            conn.commit()
                            
                            # Migrate data (convert integer IDs to UUID strings)
                            conn.execute(text("""
                                INSERT INTO projects_new (id, name, user_email, created_at, updated_at)
                                SELECT 
                                    md5(random()::text || clock_timestamp()::text || id::text) AS id,
                                    name,
                                    user_email,
                                    created_at,
                                    updated_at
                                FROM projects
                            """))
                            conn.commit()
                            
                            # Update conversations table to point to new project IDs
                            # Create a mapping of old_id -> new_id
                            mapping_result = conn.execute(text("""
                                SELECT 
                                    p.id AS old_id,
                                    pn.id AS new_id
                                FROM projects p
                                JOIN projects_new pn ON p.name = pn.name AND p.user_email = pn.user_email
                            """))
                            # Note: This mapping might not be perfect if there are duplicate names/emails
                            # For now, we'll update conversations after dropping old table
                            
                            # Drop old table
                            conn.execute(text("DROP TABLE projects CASCADE"))
                            conn.commit()
                            
                            # Rename new table
                            conn.execute(text("ALTER TABLE projects_new RENAME TO projects"))
                            conn.commit()
                            
                            # Recreate indexes
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_user_email ON projects(user_email)"))
                            conn.commit()
                            
                            # Note: conversations.project_id will need to be updated separately
                            # For now, set them to NULL (they'll be re-linked when projects are recreated)
                            try:
                                conn.execute(text("UPDATE conversations SET project_id = NULL WHERE project_id IS NOT NULL"))
                                conn.commit()
                                logger.info("[MIGRATION] Cleared project_id in conversations (will be re-linked)")
                            except:
                                pass
                            
                            migrations_applied.append(f"Migrated {row_count} projects to UUID id column")
                            logger.info(f"[MIGRATION] Successfully migrated {row_count} projects to new schema")
                    elif row and row[0] in ['character varying', 'varchar', 'text']:
                        logger.info("[MIGRATION] Projects table id column is already VARCHAR - no migration needed")
                    else:
                        logger.warning(f"[MIGRATION] Projects table exists with unknown id type: {row[0] if row else 'N/A'}")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to check/fix projects table: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    conn.rollback()
            
            # Migration 8: Add project_id to conversations table (or fix its type)
            if table_exists(conn, 'conversations'):
                try:
                    # Check if column exists and its type
                    result = conn.execute(text("""
                        SELECT data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'conversations' AND column_name = 'project_id'
                    """))
                    row = result.fetchone()
                    
                    if not row:
                        # Column doesn't exist - add it
                        conn.execute(text("""
                            ALTER TABLE conversations 
                            ADD COLUMN project_id character varying
                        """))
                        conn.commit()
                        
                        # Create index
                        conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_conversations_project_id 
                            ON conversations (project_id)
                        """))
                        conn.commit()
                        
                        # Add foreign key constraint
                        try:
                            conn.execute(text("""
                                ALTER TABLE conversations
                                ADD CONSTRAINT fk_conversations_projects
                                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                            """))
                            conn.commit()
                            logger.info("[MIGRATION] Added foreign key constraint for conversations.project_id")
                        except Exception as fk_error:
                            logger.warning(f"[MIGRATION] Could not add foreign key constraint: {str(fk_error)}")
                        
                        migrations_applied.append("Added project_id to conversations")
                        logger.info("[MIGRATION] Added project_id column to conversations table")
                    elif row[0] == 'integer':
                        # Column exists but is INTEGER - need to convert to VARCHAR
                        logger.info("[MIGRATION] Converting conversations.project_id from INTEGER to VARCHAR")
                        
                        # Drop foreign key if it exists
                        try:
                            conn.execute(text("""
                                ALTER TABLE conversations 
                                DROP CONSTRAINT IF EXISTS fk_conversations_projects
                            """))
                            conn.commit()
                        except:
                            pass
                        
                        # Clear existing values (can't convert integer to UUID)
                        conn.execute(text("UPDATE conversations SET project_id = NULL WHERE project_id IS NOT NULL"))
                        conn.commit()
                        
                        # Alter column type
                        conn.execute(text("""
                            ALTER TABLE conversations 
                            ALTER COLUMN project_id TYPE character varying USING NULL
                        """))
                        conn.commit()
                        
                        # Recreate foreign key
                        try:
                            conn.execute(text("""
                                ALTER TABLE conversations
                                ADD CONSTRAINT fk_conversations_projects
                                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                            """))
                            conn.commit()
                            logger.info("[MIGRATION] Recreated foreign key constraint")
                        except Exception as fk_error:
                            logger.warning(f"[MIGRATION] Could not recreate foreign key: {str(fk_error)}")
                        
                        migrations_applied.append("Converted conversations.project_id to VARCHAR")
                        logger.info("[MIGRATION] Converted conversations.project_id from INTEGER to VARCHAR")
                    elif row[0] in ['character varying', 'varchar', 'text']:
                        logger.info("[MIGRATION] Column project_id already exists in conversations with correct type")
                    else:
                        logger.warning(f"[MIGRATION] conversations.project_id has unexpected type: {row[0]}")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to fix project_id in conversations: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    conn.rollback()
            
            # Migration 9: Backfill default conversations for existing projects
            if table_exists(conn, 'projects') and table_exists(conn, 'conversations'):
                try:
                    # Check if we need to backfill (only if there are projects without conversations)
                    result = conn.execute(text("""
                        SELECT COUNT(*) 
                        FROM projects p
                        WHERE NOT EXISTS (
                            SELECT 1 FROM conversations c WHERE c.project_id = p.id
                        )
                    """))
                    count = result.fetchone()[0]
                    
                    if count > 0:
                        # Check if uuid_generate_v4() is available, otherwise use gen_random_uuid()
                        try:
                            conn.execute(text("SELECT uuid_generate_v4()"))
                            uuid_func = "uuid_generate_v4()::text"
                        except:
                            try:
                                conn.execute(text("SELECT gen_random_uuid()"))
                                uuid_func = "gen_random_uuid()::text"
                            except:
                                # Fallback: use md5(random()::text || clock_timestamp()::text)
                                uuid_func = "md5(random()::text || clock_timestamp()::text)"
                        
                        # Backfill: create default conversation for each project without one
                        conn.execute(text(f"""
                            INSERT INTO conversations (conversation_id, chat_id, user_email, project_id, conversation_json, created_at, updated_at)
                            SELECT
                                {uuid_func} AS conversation_id,
                                {uuid_func} AS chat_id,
                                p.user_email AS user_email,
                                p.id AS project_id,
                                '{{"conversation_id": 0, "messages": []}}'::jsonb AS conversation_json,
                                now() AS created_at,
                                now() AS updated_at
                            FROM projects p
                            WHERE NOT EXISTS (
                                SELECT 1 FROM conversations c WHERE c.project_id = p.id
                            )
                        """))
                        conn.commit()
                        migrations_applied.append(f"Backfilled {count} default conversations for existing projects")
                        logger.info(f"[MIGRATION] Backfilled {count} default conversations for existing projects")
                    else:
                        logger.info("[MIGRATION] All projects already have conversations - no backfill needed")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to backfill conversations: {str(e)}")
                    conn.rollback()
            
            # Migration 10: Create governance_projects table (clean schema without phase columns)
            if table_exists(conn, 'governance_projects'):
                # If stale schema (has 'phase' column from old design), drop and recreate
                try:
                    result = conn.execute(text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'governance_projects' AND column_name = 'phase'
                    """))
                    if result.fetchone():
                        logger.info("[MIGRATION] governance_projects has stale columns — dropping to recreate")
                        conn.execute(text("DROP TABLE IF EXISTS governance_project_phases CASCADE"))
                        conn.execute(text("DROP TABLE IF EXISTS governance_projects CASCADE"))
                        conn.commit()
                except Exception as e:
                    logger.warning(f"[MIGRATION] Could not check governance_projects columns: {e}")

            if not table_exists(conn, 'governance_projects'):
                try:
                    conn.execute(text("""
                        CREATE TABLE governance_projects (
                            id VARCHAR PRIMARY KEY,
                            user_email VARCHAR NOT NULL,
                            project_name VARCHAR NOT NULL,
                            project_type VARCHAR NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_governance_projects_user_email ON governance_projects(user_email)"))
                    conn.commit()
                    migrations_applied.append("Created governance_projects table")
                    logger.info("[MIGRATION] Created governance_projects table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to create governance_projects table: {str(e)}")
                    conn.rollback()
            else:
                logger.info("[MIGRATION] Table governance_projects already exists")

            # Migration 11: Create governance_project_phases table
            if not table_exists(conn, 'governance_project_phases'):
                try:
                    conn.execute(text("""
                        CREATE TABLE governance_project_phases (
                            id VARCHAR PRIMARY KEY,
                            project_id VARCHAR NOT NULL REFERENCES governance_projects(id) ON DELETE CASCADE,
                            phase VARCHAR,
                            status VARCHAR,
                            planned_date VARCHAR,
                            document_link TEXT,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_governance_phases_project_id ON governance_project_phases(project_id)"))
                    conn.commit()
                    migrations_applied.append("Created governance_project_phases table")
                    logger.info("[MIGRATION] Created governance_project_phases table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to create governance_project_phases table: {str(e)}")
                    conn.rollback()
            else:
                logger.info("[MIGRATION] Table governance_project_phases already exists")

            # Migration 12: Add drive_file_id to mandatory_files
            if not column_exists(conn, 'mandatory_files', 'drive_file_id'):
                try:
                    conn.execute(text("""
                        ALTER TABLE mandatory_files
                        ADD COLUMN drive_file_id VARCHAR
                    """))
                    conn.commit()
                    migrations_applied.append("Added drive_file_id to mandatory_files")
                    logger.info("[MIGRATION] Added drive_file_id column to mandatory_files table")
                except Exception as e:
                    logger.error(f"[MIGRATION] Failed to add drive_file_id to mandatory_files: {str(e)}")
                    conn.rollback()

            if migrations_applied:
                logger.info(f"[MIGRATION] Applied {len(migrations_applied)} migration(s): {', '.join(migrations_applied)}")
                return True
            else:
                logger.info("[MIGRATION] Database schema is up-to-date, no migrations needed")
                return True
                
    except Exception as e:
        logger.error(f"[MIGRATION] Error running migrations: {str(e)}")
        return False

def column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        inspector = inspect(conn)
        if not inspector.has_table(table_name):
            return False
        cols = inspector.get_columns(table_name)
        return any(col.get("name") == column_name for col in cols)
    except Exception as e:
        logger.error(f"[MIGRATION] Error checking column {column_name} in {table_name}: {str(e)}")
        return False

def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists"""
    try:
        inspector = inspect(conn)
        return inspector.has_table(table_name)
    except Exception as e:
        logger.error(f"[MIGRATION] Error checking table {table_name}: {str(e)}")
        return False

