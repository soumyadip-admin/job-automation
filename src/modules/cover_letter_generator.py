"""
Cover Letter Generator - Creates personalized cover letters
"""
from datetime import datetime

class CoverLetterGenerator:
    """Generates customized cover letters for job applications."""
    
    def __init__(self):
        self.user_name = "Soumyadip Sarkar"
        self.user_phone = "6363793581"
        self.user_email = "soumyadipsarkar2106@gmail.com"
        self.user_linkedin = "linkedin.com/in/soumyadip-sarkar-1169aa131"
    
    def generate(self, job_title, company_name, matched_skills):
        """
        Generate a personalized cover letter.
        
        Args:
            job_title: The job position
            company_name: Company name
            matched_skills: List of skills that matched
        
        Returns:
            Formatted cover letter string
        """
        # Format skills for display
        if matched_skills and len(matched_skills) > 0:
            skills_text = ", ".join([s.title() for s in matched_skills[:4]])
        else:
            skills_text = "SQL, Excel, Tableau, and Python"
        
        # Select relevant project based on common keywords
        project_paragraph = self._select_project_paragraph(job_title)
        
        letter = f"""Dear Hiring Manager,

I am writing to express my enthusiastic interest in the {job_title} position at {company_name}. As a Google-certified Data Analyst with demonstrated expertise in {skills_text}, I am confident in my ability to contribute meaningfully to your data analytics initiatives.

In my recent role at Alorica, I managed and maintained data integrity across 1,000+ customer records, improving data quality by 15% through systematic validation processes. This hands-on experience strengthened my attention to detail and analytical problem-solving skills.

{project_paragraph}

My technical toolkit includes SQL, Excel, Python, R, Tableau, and Power BI. Through my portfolio of 5 end-to-end analytics projects analyzing over 700,000 records across diverse industries, I have developed a strong foundation in the complete data analytics lifecycle.

I am excited about the opportunity at {company_name} and eager to bring my analytical mindset to your team.

Thank you for considering my application.

Best regards,
{self.user_name}
Phone: {self.user_phone}
Email: {self.user_email}
LinkedIn: {self.user_linkedin}"""
        
        return letter.strip()
    
    def _select_project_paragraph(self, job_title):
        """Select most relevant project based on job title."""
        title_lower = job_title.lower()
        
        if any(word in title_lower for word in ['finance', 'bank', 'loan', 'risk']):
            return """In my Financial Risk and Loan Default Analysis project, I analyzed 120,000+ loan records using SQL and R to identify default patterns. I discovered key insights including the Employment Paradox, demonstrating my ability to uncover actionable business intelligence."""
        
        elif any(word in title_lower for word in ['retail', 'ecommerce', 'sales']):
            return """My Retail Sales Performance Analysis involved processing 500,000+ transactions to understand revenue patterns. I built comprehensive Tableau dashboards revealing seasonal trends and customer behavior insights."""
        
        elif any(word in title_lower for word in ['telecom', 'churn', 'customer']):
            return """In my Telecom Customer Churn Analysis, I delivered end-to-end analytics on 7,043 customers, identifying high-risk segments through statistical testing and building interactive dashboards with actionable retention strategies."""
        
        else:
            return """In my Vehicle Pricing Analytics project, I analyzed 7,994 automotive records using regression modeling (R² = 0.72) and ANOVA testing. I created sophisticated Tableau visualizations to communicate pricing dynamics to stakeholders."""
    
    def save_to_file(self, letter, company_name, job_title, output_dir="cover_letters"):
        """Save cover letter to a file."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Clean filename
        safe_company = "".join(c if c.isalnum() else "_" for c in company_name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/CL_{safe_company}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(letter)
        
        return filename


# Test if run directly
if __name__ == "__main__":
    gen = CoverLetterGenerator()
    
    letter = gen.generate(
        job_title="Junior Data Analyst",
        company_name="TechCorp Solutions",
        matched_skills=["sql", "excel", "tableau", "python"]
    )
    
    print(letter)