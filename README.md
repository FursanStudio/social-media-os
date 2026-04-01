# Social Media OS

## Project Overview
**Social Media OS** is an AI-powered autonomous social media content management system developed as part of an internship project under **FursanStudio**.  
The system is designed to help brands and individuals manage their social media content efficiently by automating content creation, scheduling, and organization.

This project combines front-end interface, back-end automation, and AI-powered content generation to provide a structured social media workflow.

---

## Key Features
- AI-generated social media content tailored for specific brands or topics
- Automated image generation for social media posts
- Content approval and reliability checks
- Scheduling and posting framework (for multiple platforms)
- Dashboard interface for monitoring tasks
- Modular architecture for easy expansion and maintenance

---

## Functional Modules
- **Content Generation**: Produces text for posts using AI algorithms  
- **Image Generation**: Creates custom visuals for social media  
- **Scheduling & Autopilot**: Automatically plans and schedules posts  
- **Platform Integration**: Includes support for platforms like Instagram and LinkedIn  
- **Brand Memory**: Maintains context and brand consistency across posts  
- **Approval Workflow**: Queue-based system for verifying content before publishing  
- **Scraping & Research**: Gathers relevant content and insights for post creation  

---

## Technologies Used
- **Python** – Core logic and AI modules  
- **HTML / CSS / JavaScript** – Frontend interface and dashboard  
- **SQLite / JSON** – Data storage for schedules and approvals  
- **Docker & Docker Compose** – Deployment and environment setup  
- **Cloud Build** – Automation for deployment pipelines  

---

## Project Structure
```text
social media OS/
│── index.html             # Frontend dashboard
│── style.css
│── script.js
│── echo_api.py            # Core API module
│── echo_autopilot.py      # Automation engine
│── echo_pipeline.py       # Post processing pipeline
│── echo_scheduler.py      # Scheduling engine
│── echo_publisher.py      # Posting module
│── echo_content_writer.py # Content generator
│── echo_brand_memory.py   # Brand consistency module
│── echo_reliability.py    # Content verification
│── echo_scraper.py        # Research & scraping
│── image_generator.py     # AI image generation
│── instagram_poster.py    # Instagram posting endpoint
│── linkedin_endpoints.py  # LinkedIn posting endpoint
│── Dockerfile
│── docker-compose.yml
│── cloudbuild.yaml
│── echo_schedule.db       # Schedule database
│── approval_queue.json    # Approval queue
│── .env                   # Environment variables
│── setup_everything.py    # Project setup
│── README.md              # Project documentation

How to Run
Clone or download this repository
Set up the environment using .env and setup_everything.py
Run the main system modules or launch the front-end dashboard:
Open index.html in a browser for UI
Run Python modules for automation and AI content generation
For full deployment, use Docker and Docker Compose
Learning Outcomes
Advanced front-end and back-end integration
AI-powered content creation and workflow automation
Git and GitHub project management for internships
Docker-based deployment pipelines
Modular and scalable software architecture
Future Improvements
Real-time posting to multiple platforms
User authentication and multi-user support
Analytics dashboard with engagement metrics
Integration with additional social media APIs
More robust AI models for content creation
Internship / Repository Information

This project was developed and uploaded as part of an internship task under:

FursanStudio

Author

Aoraza
