import logging
import os
import uuid
from datetime import datetime , timedelta 
from dotenv import load_dotenv
load_dotenv()

class SessionHistoryManager:
    def __init__(self, mongo_client):
        
        try:
            self.chat_collection = mongo_client.chatbot_db[os.getenv("BA_CHAT_COLLECTION")]
 
        except Exception as e:
            logging.error(f"Error in MongoDB connection: {e}")
            raise

    @staticmethod
    def create_session():
        """Generate a new session ID."""
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def append_message(self, session_id, role, content ,job_id=None, file = None ):
        try:
            doc = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow()
            }
            
            if file:
                doc["file"] = file
                
            if job_id:
                doc["job_id"] = job_id
                
            insert_result = self.chat_collection.insert_one(doc)
            return insert_result.inserted_id
        except Exception as e:
            logging.error(f"Error in append_message: {e}")
            raise 
    
    #Todo: when we need multiple conversations in single workflow-job
    def get_recent_sessions_by_job_id(self,job_id):
        pass
    
    def get_recent_sessions_by_ttl(self, current_time: datetime, ttl_seconds:float = 900):
        # Compute cutoff time
        cutoff_time = current_time - timedelta(seconds=ttl_seconds)
        
        pipeline = [
            {"$match": {
                "timestamp": {"$gte": cutoff_time}
            }},
            {"$group": {
                "_id": "$session_id",
                "latest_timestamp": {"$max": "$timestamp"}
            }},
            {"$sort": {"latest_timestamp": -1}}
        ]

        try:
            sessions = list(self.chat_collection.aggregate(pipeline))
            # print(sessions)
            return [str(s["_id"]) for s in sessions]
        except Exception as e:
            logging.error(f"Error in get_recent_sessions_by_ttl: {e}")
            raise
    
    def get_recent_sessions(self, limit=1000 ):
        try:
        
            query = {"job_id": None}

            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": "$session_id",
                    "latest_timestamp": {"$max": "$timestamp"}
                }},
                {"$sort": {"latest_timestamp": -1}},  # Sort by latest timestamp descending
                {"$limit": limit}  # Replace `limit` with the number of sessions you want
            ]

            sessions = list(self.chat_collection.aggregate(pipeline))
            session_ids = [str(s["_id"]) for s in sessions]
            return session_ids
        except Exception as e:
            logging.error(f"Error in get_recent_sessions: {e}")
            raise 
        
    def load_history(self, session_id ,limit = None):
        try:
            query = {"session_id": session_id}
            messages = list(self.chat_collection.find(query).sort("timestamp", 1))
            
            if limit:
                messages = messages[-limit:]
                
            return [{"role": m["role"], "content": m["content"], "timestamp": m["timestamp"], **({'file': m['file']} if 'file' in m else {})} for m in messages]

        except Exception as e:
            logging.error(f"Error in load_history: {e}")
            raise 
        
    def delete_session(self, session_id):
        try:
            query = {
                "session_id": session_id
            }
            
            delete_result = self.chat_collection.delete_many(query)
            return {
                "deleted_count": delete_result.deleted_count,
                "status": "success" if delete_result.deleted_count > 0 else "no records found"
            }
        except Exception as e:
            logging.error(f"Error in delete_session: {e}")
            raise 
                  
class SessionContextManager:
    def __init__(self, mongo_client):
        try:
            self.chat_collection = mongo_client.chatbot_db[os.getenv("BA_SESSION_CONTEXT")]
           
        except Exception as e:
            logging.error(f"Error in MongoDB connection: {e}")
            raise

    def set_context(self , session_id:str, context:dict):
        
        filter = {"session_id": session_id}
        update = {"$set": {**context, "timestamp": datetime.utcnow()}}
        
        try:
            result = self.chat_collection.update_one(filter, update, upsert=True)
            if result.upserted_id:
                return {
                    "status": "success",
                    "operation": "created",
                    "upserted_id": str(result.upserted_id)
                }
            else:
                return {
                    "status": "success",
                    "operation": "updated",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count
                }
        except Exception as e:
            logging.error(f"Error in set_context: {e}")
            raise
        
    
    def get_context(self, session_id):
        try:
            query = {"session_id": session_id}
            context_doc = self.chat_collection.find_one(query)
            if context_doc:
                # print("context_doc:",{**context_doc})
                context_doc.pop("_id", None)
                return {"status":"success",**context_doc}
            else:
                return {"status":"success","context":" Session context is empty "}
        except Exception as e:
            logging.error(f"Error in get_context: {e}")
            raise
    
    def delete_context(self, session_id):
        try:
            query = {
                "session_id": session_id
            }
            
            delete_result = self.chat_collection.delete_many(query)
            return {
                "deleted_count": delete_result.deleted_count,
                "status": "success" if delete_result.deleted_count > 0 else "no records found"
            }
        except Exception as e:
            logging.error(f"Error in delete_context: {e}")
            raise
        
class UserConfigManager:
    def __init__(self, mongo_client):
        try:
            self.config_collection = mongo_client.chatbot_db[os.getenv("BA_USER_CONFIG_COLLECTION")]
           
        except Exception as e:
            logging.error(f"Error in MongoDB connection: {e}")
            raise

    def set_config(self , config:dict):
        
        """
        update existing fields or create new fields for a user config in the workspace. 
        config fields:
        {
            "output_style": "brief" / "narrative" / "descriptive",
            "user_story_format": "jtbd" / "connextra" / "gherkin",
            "jira-username":"your-jira-username",
            "jira-apitoken":"your-jira-api-token",  
        }
        """ 
        
        
        # Build filter to match user config
        filter = {}
        # Merge new config fields with existing fields, keeping old fields unchanged unless updated
        existing = self.config_collection.find_one(filter)
        merged_fields = existing if existing else {}
        merged_fields.update(config)
        # Remove _id if present to avoid update errors
        merged_fields.pop("_id", None)
        update = {"$set": merged_fields}
        
        try:
            result = self.config_collection.update_one(filter, update, upsert=True)
            if result.upserted_id:
                return {
                    "status": "success",
                    "operation": "created",
                    "upserted_id": str(result.upserted_id)
                }
            else:
                return {
                    "status": "success",
                    "operation": "updated",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count
                }
        except Exception as e:
            logging.error(f"Error in set_config: {e}")
            raise
        
    
    def get_config(self, fields: list = None):
        try:
            query = {}
            config_doc = self.config_collection.find_one(query)
            if config_doc:
                # Remove MongoDB internal _id field
                config_doc.pop("_id", None)
                if fields is None:
                    return config_doc
                else:
                    return {field: config_doc.get(field) for field in fields}
            else:
                return {}
        except Exception as e:
            logging.error(f"Error in get_config: {e}")
            raise 

class WorkflowContextManager:
    def __init__(self, mongo_client):
        try:
            collection_name = os.getenv("WORKFLOW_COLLECTION_NAME")
            if not collection_name:
                raise ValueError("WORKFLOW_COLLECTION_NAME environment variable is not set.")
            self.workflow_collection = mongo_client.workflow_db[collection_name]
            
        except Exception as e:
            logging.error(f"Error in MongoDB connection: {e}")
            raise 

    def curate_context(self, job_id:str , agent_feed:list):
        
        """
        This function creates context from job_id artifacts.
        Arguments:
            job_id(str): unique job_id to curate context from.
            agent_feed(list): list of items for agent context.
        Returns:
            String containing the context for workflow task.
        """
        
        try:
            # Fetch the job document from workflow collection
            query = {
                "job_id": job_id
            }
            
            job_doc = self.workflow_collection.find_one(query)
            
            if not job_doc:
                logging.warning(f"No job found for job_id: {job_id}")
                return "No workflow context found for the given job_id."
            
            # Extract relevant context based on agent_feed
            context_parts = []
            context_parts_empty = []
            for feed_item in agent_feed:
                if feed_item in job_doc['job_artifacts']:
                    context_parts.append(f"{feed_item}: {job_doc['job_artifacts'][feed_item]}")
                else:
                    context_parts_empty.append(f"{feed_item}: Ask the user to input this artifact to proceed.")
            
            # Combine all context parts into a single string
            context_string = "\n".join(context_parts_empty + context_parts)
            print(f"project context: \n {context_string}")
            return context_string
            
        except Exception as e:
            logging.error(f"Error in curate_context: {e}")
            raise
                      
            
            
