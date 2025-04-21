import os
import smtplib
import json
import uuid
import datetime
import pathlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Dict, Any, Optional, Union

class AgentTools:
    """
    A collection of tools for the Maxwell AI agent to perform various actions
    such as sending emails, taking notes, scheduling meetings, etc.
    """
    
    def __init__(self, working_dir: str = "agent_data"):
        """
        Initialize the agent tools with a working directory
        
        Args:
            working_dir: Directory to store tool data (notes, templates, etc.)
        """
        self.working_dir = pathlib.Path(working_dir)
        self.notes_dir = self.working_dir / "notes"
        self.templates_dir = self.working_dir / "templates"
        self.calendar_dir = self.working_dir / "calendar"
        
        # Create necessary directories
        self._setup_directories()
        
        # Email configuration
        self.email_config = self._load_email_config()
        
        # Templates
        self.email_templates = self._load_templates("email")
        self.followup_templates = self._load_templates("followup")
        
    def _setup_directories(self):
        """Create necessary directories for the agent tools"""
        directories = [
            self.working_dir,
            self.notes_dir, 
            self.templates_dir,
            self.calendar_dir
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True, parents=True)
            
        # Create default templates if they don't exist
        self._create_default_templates()
    
    def _create_default_templates(self):
        """Create default email and followup templates"""
        default_templates = {
            "email_proposal.txt": """Subject: AI Strategy Proposal for {company_name}

Dear {contact_name},

Thank you for our conversation about {pain_point}. As discussed, Critical Future can help with:

1. {solution_point_1}
2. {solution_point_2}
3. {solution_point_3}

I've attached a brief overview of our approach. Would you be available for a 30-minute call next week to discuss this further?

Best regards,
Maxwell
Critical Future LTD
            """,
            
            "email_followup.txt": """Subject: Following up on our conversation about {topic}

Dear {contact_name},

I hope this email finds you well. I wanted to follow up on our recent conversation about {topic} and {company_name}'s challenges with {pain_point}.

Would you be interested in scheduling a brief call with one of our specialists to explore potential solutions?

Best regards,
Maxwell
Critical Future LTD
            """,
            
            "followup_call.txt": """
Key points to discuss on the follow-up call with {contact_name} from {company_name}:

1. Recap of previous conversation about {pain_point}
2. Present our solution approach for {solution_area}
3. Discuss timeline and expected outcomes
4. Next steps and potential engagement options
            """
        }
        
        for filename, content in default_templates.items():
            template_path = self.templates_dir / filename
            if not template_path.exists():
                with open(template_path, "w") as f:
                    f.write(content)
    
    def _load_email_config(self) -> Dict[str, Any]:
        """Load email configuration from environment variables or config file"""
        config_path = self.working_dir / "email_config.json"
        
        # Default config
        default_config = {
            "smtp_server": os.getenv("AGENT_SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("AGENT_SMTP_PORT", "587")),
            "sender_email": os.getenv("AGENT_EMAIL", ""),
            "sender_name": os.getenv("AGENT_NAME", "Maxwell - Critical Future"),
            "email_password": os.getenv("AGENT_EMAIL_PASSWORD", "")
        }
        
        # If config file exists, load it
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    # Update with environment variables if they exist
                    for key in default_config:
                        if os.getenv(f"AGENT_{key.upper()}"):
                            config[key] = default_config[key]
                    return config
            except Exception as e:
                print(f"Error loading email config: {e}")
                return default_config
        else:
            # Create config file with default values
            try:
                with open(config_path, "w") as f:
                    json.dump(default_config, f, indent=2)
            except Exception as e:
                print(f"Error creating email config: {e}")
            
            return default_config
    
    def _load_templates(self, template_type: str) -> Dict[str, str]:
        """Load templates of a specific type"""
        templates = {}
        template_files = list(self.templates_dir.glob(f"{template_type}_*.txt"))
        
        for template_file in template_files:
            name = template_file.stem.replace(f"{template_type}_", "")
            try:
                templates[name] = template_file.read_text()
            except Exception as e:
                print(f"Error loading template {template_file}: {e}")
        
        return templates
    
    def take_note(self, contact_name: str, company_name: str, note_content: str, 
                 tags: List[str] = None) -> Dict[str, Any]:
        """
        Take a note about a conversation or contact
        
        Args:
            contact_name: Name of the contact
            company_name: Name of the company
            note_content: Content of the note
            tags: Optional list of tags for categorization
            
        Returns:
            Dict containing the note information and status
        """
        if tags is None:
            tags = []
            
        # Create note ID and filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        note_id = f"note_{timestamp}_{uuid.uuid4().hex[:8]}"
        note_file = self.notes_dir / f"{note_id}.json"
        
        # Create note data
        note_data = {
            "id": note_id,
            "contact_name": contact_name,
            "company_name": company_name,
            "content": note_content,
            "tags": tags,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }
        
        # Save the note
        try:
            with open(note_file, "w") as f:
                json.dump(note_data, f, indent=2)
            
            return {
                "status": "success",
                "message": f"Note created successfully with ID: {note_id}",
                "note": note_data
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create note: {str(e)}"
            }
    
    def get_notes(self, contact_name: Optional[str] = None, 
                 company_name: Optional[str] = None,
                 tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Retrieve notes based on filters
        
        Args:
            contact_name: Optional filter by contact name
            company_name: Optional filter by company name
            tags: Optional filter by tags
            
        Returns:
            Dict containing matching notes and status
        """
        notes = []
        
        try:
            for note_file in self.notes_dir.glob("note_*.json"):
                try:
                    with open(note_file, "r") as f:
                        note_data = json.load(f)
                    
                    # Apply filters
                    if contact_name and contact_name.lower() not in note_data["contact_name"].lower():
                        continue
                    
                    if company_name and company_name.lower() not in note_data["company_name"].lower():
                        continue
                    
                    if tags:
                        # Check if any of the requested tags match
                        if not any(tag in note_data["tags"] for tag in tags):
                            continue
                    
                    notes.append(note_data)
                except Exception as e:
                    print(f"Error reading note file {note_file}: {e}")
            
            return {
                "status": "success",
                "count": len(notes),
                "notes": notes
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to retrieve notes: {str(e)}",
                "notes": []
            }
    
    def send_email(self, to_email: str, 
                  subject: str, 
                  body: str,
                  cc: List[str] = None,
                  bcc: List[str] = None,
                  attachments: List[str] = None,
                  template_name: Optional[str] = None,
                  template_variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Send an email to a contact
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            attachments: Optional list of file paths to attach
            template_name: Optional template name to use
            template_variables: Optional variables for template
            
        Returns:
            Dict containing status and message
        """
        if cc is None:
            cc = []
        if bcc is None:
            bcc = []
        if attachments is None:
            attachments = []
        if template_variables is None:
            template_variables = {}
        
        # Check if email configuration is valid
        if not self.email_config["sender_email"] or not self.email_config["email_password"]:
            return {
                "status": "error",
                "message": "Email configuration is incomplete. Please set AGENT_EMAIL and AGENT_EMAIL_PASSWORD."
            }
        
        # If template is specified, use it
        if template_name and template_name in self.email_templates:
            template = self.email_templates[template_name]
            
            # Apply template variables
            for key, value in template_variables.items():
                template = template.replace(f"{{{key}}}", value)
            
            # Extract subject from template if it starts with "Subject: "
            if template.startswith("Subject:"):
                subject_line, body_content = template.split("\n", 1)
                subject = subject_line.replace("Subject:", "").strip()
                body = body_content.strip()
            else:
                body = template
        
        # Create the email message
        message = MIMEMultipart()
        message["From"] = f"{self.email_config['sender_name']} <{self.email_config['sender_email']}>"
        message["To"] = to_email
        message["Subject"] = subject
        
        if cc:
            message["Cc"] = ", ".join(cc)
        if bcc:
            message["Bcc"] = ", ".join(bcc)
        
        # Attach the body content
        message.attach(MIMEText(body, "plain"))
        
        # Add attachments
        for attachment_path in attachments:
            try:
                with open(attachment_path, "rb") as file:
                    attachment = MIMEApplication(file.read())
                    attachment_name = os.path.basename(attachment_path)
                    attachment.add_header(
                        "Content-Disposition", 
                        f"attachment; filename={attachment_name}"
                    )
                    message.attach(attachment)
            except Exception as e:
                print(f"Error attaching file {attachment_path}: {e}")
        
        # Try to send the email
        try:
            with smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.starttls()
                server.login(self.email_config["sender_email"], self.email_config["email_password"])
                
                # Collect all recipients
                all_recipients = [to_email] + cc + bcc
                
                server.sendmail(
                    self.email_config["sender_email"],
                    all_recipients,
                    message.as_string()
                )
            
            # Log the sent email
            self._log_email(to_email, subject, cc, bcc)
            
            return {
                "status": "success",
                "message": f"Email sent successfully to {to_email}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to send email: {str(e)}"
            }
    
    def _log_email(self, to_email: str, subject: str, cc: List[str], bcc: List[str]):
        """Log sent emails"""
        log_dir = self.working_dir / "email_logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "email_log.json"
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "to": to_email,
            "subject": subject,
            "cc": cc,
            "bcc": bcc
        }
        
        # Load existing log or create new one
        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    log_data = json.load(f)
            except:
                log_data = {"emails": []}
        else:
            log_data = {"emails": []}
        
        # Add new entry and save
        log_data["emails"].append(log_entry)
        
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)
    
    def schedule_meeting(self, contact_name: str, email: str, 
                         date: str, time: str, duration: int,
                         topic: str, meeting_type: str = "zoom") -> Dict[str, Any]:
        """
        Schedule a meeting with a contact
        
        Args:
            contact_name: Name of the contact
            email: Email of the contact
            date: Date of the meeting (YYYY-MM-DD)
            time: Time of the meeting (HH:MM)
            duration: Duration in minutes
            topic: Meeting topic
            meeting_type: Type of meeting (zoom, teams, etc.)
            
        Returns:
            Dict containing status and meeting details
        """
        # This is a placeholder - in a real implementation, 
        # this would integrate with calendar APIs (Google Calendar, Outlook, etc.)
        
        meeting_id = f"meeting_{uuid.uuid4().hex[:8]}"
        calendar_file = self.calendar_dir / f"{meeting_id}.json"
        
        meeting_data = {
            "id": meeting_id,
            "contact_name": contact_name,
            "email": email,
            "date": date,
            "time": time,
            "duration": duration,
            "topic": topic,
            "meeting_type": meeting_type,
            "scheduled_at": datetime.datetime.now().isoformat(),
            "status": "scheduled"
        }
        
        try:
            with open(calendar_file, "w") as f:
                json.dump(meeting_data, f, indent=2)
            
            return {
                "status": "success",
                "message": f"Meeting scheduled successfully for {date} at {time}",
                "meeting": meeting_data
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to schedule meeting: {str(e)}"
            }
    
    def create_followup_task(self, contact_name: str, company_name: str,
                           followup_date: str, followup_type: str,
                           notes: str = "") -> Dict[str, Any]:
        """
        Create a follow-up task for a contact
        
        Args:
            contact_name: Name of the contact
            company_name: Name of the company
            followup_date: Date for the follow-up (YYYY-MM-DD)
            followup_type: Type of follow-up (call, email, etc.)
            notes: Additional notes for the follow-up
            
        Returns:
            Dict containing status and task details
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        tasks_dir = self.working_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        
        task_file = tasks_dir / f"{task_id}.json"
        
        task_data = {
            "id": task_id,
            "contact_name": contact_name,
            "company_name": company_name,
            "followup_date": followup_date,
            "followup_type": followup_type,
            "notes": notes,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "pending"
        }
        
        try:
            with open(task_file, "w") as f:
                json.dump(task_data, f, indent=2)
            
            return {
                "status": "success",
                "message": f"Follow-up task created for {followup_date}",
                "task": task_data
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create follow-up task: {str(e)}"
            }
    
    def generate_proposal(self, company_name: str, contact_name: str,
                         pain_points: List[str], solutions: List[str],
                         timeline: str, budget_range: str) -> Dict[str, Any]:
        """
        Generate a sales proposal based on conversation
        
        Args:
            company_name: Company name
            contact_name: Contact name
            pain_points: List of identified pain points
            solutions: List of proposed solutions
            timeline: Project timeline
            budget_range: Estimated budget range
            
        Returns:
            Dict containing status and proposal details
        """
        proposal_id = f"proposal_{uuid.uuid4().hex[:8]}"
        proposals_dir = self.working_dir / "proposals"
        proposals_dir.mkdir(exist_ok=True)
        
        proposal_file = proposals_dir / f"{proposal_id}.json"
        
        # Create basic proposal structure
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        proposal_data = {
            "id": proposal_id,
            "company_name": company_name,
            "contact_name": contact_name,
            "date": today,
            "pain_points": pain_points,
            "solutions": solutions,
            "timeline": timeline,
            "budget_range": budget_range,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "draft"
        }
        
        try:
            with open(proposal_file, "w") as f:
                json.dump(proposal_data, f, indent=2)
            
            # In a real implementation, this might generate a PDF document
            
            return {
                "status": "success",
                "message": f"Proposal generated for {company_name}",
                "proposal": proposal_data,
                "file_path": str(proposal_file)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to generate proposal: {str(e)}"
            }
            
    def search_knowledge_base(self, query: str, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Search the company knowledge base for information
        
        Args:
            query: Search query
            category: Optional category to search within
            
        Returns:
            Dict containing search results
        """
        # This is a placeholder - in a real implementation,
        # this would connect to a knowledge base or database
        
        # Simulated results for demonstration
        mock_results = {
            "AI Strategy": [
                {
                    "title": "AI Strategy Framework",
                    "content": "Our AI strategy framework includes assessment, roadmap development, and implementation planning.",
                    "relevance": 0.95
                },
                {
                    "title": "AI ROI Calculator",
                    "content": "Method for calculating return on investment for AI initiatives based on industry benchmarks.",
                    "relevance": 0.85
                }
            ],
            "Digital Transformation": [
                {
                    "title": "Digital Maturity Assessment",
                    "content": "Framework for assessing an organization's digital maturity across key dimensions.",
                    "relevance": 0.9
                },
                {
                    "title": "Change Management Playbook",
                    "content": "Guide for managing organizational change during digital transformation initiatives.",
                    "relevance": 0.8
                }
            ],
            "Market Intelligence": [
                {
                    "title": "Competitive Analysis Framework",
                    "content": "Methodology for analyzing competitors and market positioning.",
                    "relevance": 0.88
                },
                {
                    "title": "Industry Trend Reports",
                    "content": "Quarterly reports on emerging trends across key industries.",
                    "relevance": 0.82
                }
            ]
        }
        
        # Filter by category if provided
        if category and category in mock_results:
            results = mock_results[category]
        else:
            # Flatten all results if no category specified
            results = []
            for cat_results in mock_results.values():
                results.extend(cat_results)
            
            # Sort by relevance
            results.sort(key=lambda x: x["relevance"], reverse=True)
        
        return {
            "status": "success",
            "query": query,
            "category": category,
            "results_count": len(results),
            "results": results
        } 