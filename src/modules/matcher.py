"""
Job Matcher - Enhanced for detailed skills and synonyms
"""
import json
import re

class JobMatcher:
    """Calculates how well a job matches user's profile."""
    
    def __init__(self, config_path='config/config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.my_skills = set(s.lower() for s in self.config.get('skills', []))
        self.target_roles = [r.lower() for r in self.config.get('target_roles', [])]
        self.exclusions = [e.lower() for e in self.config.get('exclusion_keywords', [])]
        self.thresholds = self.config.get('matching', {})
        self.seniority_pattern = re.compile(r'\b(senior|sr\.?|lead|manager|director|vice president|vp|principal|head)\b', re.I)
        
        # Enhanced skill synonyms and variations
        self.skill_synonyms = {
            # SQL Variations
            'sql': ['sql', 'sqlite', 'mysql', 't-sql', 'postgresql', 'oracle', 'database', 'queries', 'query'],
            
            # Excel Variations
            'excel': ['excel', 'ms excel', 'microsoft excel', 'pivot tables', 'vlookup', 'data validation', 'spreadsheet'],
            
            # Tableau Variations
            'tableau': ['tableau', 'tableau desktop', 'tableau server', 'tableau dashboard', 'visualization', 'viz'],
            
            # Power BI Variations
            'power bi': ['power bi', 'powerbi', 'power-bi', 'pbi', 'msbi', 'microsoft bi'],
            
            # R Programming Variations
            'r': ['r', 'r programming', 'rstudio', 'r, ', 'dplyr', 'ggplot2', 'tidyverse', 'shiny'],
            
            # Python Variations
            'python': ['python', 'python3', 'pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn'],
            
            # Data Analysis Variations
            'data analysis': ['data analysis', 'data analytics', 'analytics', 'analyze data', 'data analyst'],
            
            # Statistical Analysis
            'statistical analysis': ['statistical', 'statistics', 'stats', 'anova', 'regression', 'hypothesis testing'],
            
            # Data Cleaning
            'data cleaning': ['data cleaning', 'data preprocessing', 'preprocessing', 'cleaning', 'wrangling'],
            
            # EDA
            'eda': ['eda', 'exploratory data analysis', 'exploratory'],
            
            # Data Visualization
            'data visualization': ['data visualization', 'visualization', 'visualize', 'charts', 'graphs', 'dashboards'],
            
            # Database
            'database': ['database', 'db', 'sql', 'queries', 'data modeling', 'schema'],
            
            # Reporting
            'reporting': ['reporting', 'reports', 'mis', 'mis reporting', 'kpi', 'dashboard'],
            
            # Machine Learning
            'machine learning': ['machine learning', 'ml', 'predictive', 'predictive analytics', 'modeling'],
            
            # Customer Analysis
            'customer analysis': ['customer', 'customer segmentation', 'behavioral', 'customer insights', 'churn'],
            
            # Business Intelligence
            'bi': ['bi', 'business intelligence', 'intelligence', 'analytics'],
            
            # Operations
            'operations': ['operations', 'operational', 'supply chain'],
            
            # Marketing
            'marketing': ['marketing', 'market', 'customer journey', 'segmentation'],
            
            # Risk
            'risk': ['risk', 'credit risk', 'risk assessment', 'fraud'],
            
            # Git
            'git': ['git', 'version control', 'github', 'bitbucket'],
            
            # Office
            'office': ['microsoft office', 'ms office', 'google sheets', 'sheets', 'word', 'powerpoint']
        }
        
        # Skill groups for bonus scoring
        self.skill_groups = {
            'core_data': ['sql', 'python', 'r', 'excel'],
            'visualization': ['tableau', 'power bi', 'data visualization'],
            'analysis': ['data analysis', 'statistical analysis', 'predictive analytics'],
            'tools': ['git', 'microsoft office', 'google sheets']
        }
    
    def should_exclude(self, job_title, job_description=''):
        """Check if job should be excluded."""
        text = f"{job_title} {job_description}".lower()
        
        for keyword in self.exclusions:
            if re.search(rf'(?<!\w){re.escape(keyword)}(?!\w)', text):
                return True, keyword
        if self.seniority_pattern.search(job_title):
            return True, 'senior/managerial title'
        return False, None

    @staticmethod
    def _contains_term(text, term):
        """Match tokens/phrases, never one-character substrings inside normal words."""
        return bool(re.search(rf'(?<!\w){re.escape(term.lower())}(?!\w)', text.lower()))
    
    def _extract_skills(self, text):
        """Extract only explicit, boundary-safe skills from title/JD text."""
        found_skills = set()
        for skill in self.my_skills:
            if self._contains_term(text, skill):
                found_skills.add(skill)
        for main_skill, synonyms in self.skill_synonyms.items():
            if any(self._contains_term(text, synonym) for synonym in synonyms):
                found_skills.add(main_skill)
        return found_skills
    
    def calculate_score(self, job_title, job_description=''):
        """Calculate enhanced match score."""
        job_title_lower = job_title.lower()
        job_desc_lower = job_description.lower() if job_description else ''
        combined_text = f"{job_title_lower} {job_desc_lower}"
        
        # Step 1: Check exclusions
        excluded, reason = self.should_exclude(job_title, job_description)
        if excluded:
            return 0, [], 'exclude', f"Contains: {reason}"
        
        # Step 2: Title Match (50% weight) - Increased importance
        title_score = 0
        
        # Exact role match
        for role in self.target_roles:
            if role in job_title_lower:
                title_score = 100
                break
        
        # Partial matches with scoring
        if title_score == 0:
            title_keywords = {
                'junior data analyst': 100,
                'jr. data analyst': 100,
                'jr data analyst': 100,
                'data analyst': 95,
                'data analytics analyst': 90,
                'analyst - data analytics': 90,
                'analyst-data analytics': 90,
                'reporting and analytics': 90,
                'reporting & analytics': 90,
                'mis analyst': 95,
                'mis executive': 90,
                'reporting analyst': 95,
                'reporting executive': 85,
                'business intelligence analyst': 95,
                'bi analyst': 90,
                'operations analyst': 85,
                'operations analytics': 85,
                'workforce analyst': 90,
                'wfm analyst': 90,
                'workforce management analyst': 90,
                'insights analyst': 85,
                'junior business analyst': 85
            }
            
            for keyword, score in title_keywords.items():
                if keyword in job_title_lower:
                    title_score = max(title_score, score)
        
        # Require an actual target-role title; title-only cards must not earn skills credit.
        if title_score == 0:
            return 0, [], 'skip', 'Title is outside the target analyst/BI/MIS/reporting roles'
        if self._contains_term(job_title_lower, 'junior'):
            title_score = min(100, title_score + 10)
        if self._contains_term(job_title_lower, 'analyst'):
            title_score = min(100, title_score + 5)
        
        # Step 3: Skills Match (50% weight)
        found_skills = self._extract_skills(job_desc_lower)  # Never infer skills from the job title alone.
        matched_skills = list(found_skills)
        
        # Enhanced skill scoring
        skill_count = len(matched_skills)
        
        if skill_count >= 10:
            skill_score = 100
        elif skill_count >= 8:
            skill_score = 95
        elif skill_count >= 6:
            skill_score = 90
        elif skill_count >= 5:
            skill_score = 85
        elif skill_count >= 4:
            skill_score = 80
        elif skill_count >= 3:
            skill_score = 75
        elif skill_count >= 2:
            skill_score = 70
        elif skill_count >= 1:
            skill_score = 60
        else:
            skill_score = 0  # No JD evidence means no invented skill match.
        
        # Small diversity bonus only for explicitly observed skills.
        group_bonus = 0
        for group_skills in self.skill_groups.values():
            if any(skill in found_skills for skill in group_skills):
                group_bonus += 3
        skill_score = min(100, skill_score + group_bonus)
        
        # Step 4: Calculate weighted total
        total_score = int((title_score * 0.5) + (skill_score * 0.5))
        
        # Step 5: Bonus points
        # Location bonus (if preferred location)
        location_bonus = 0
        
        # Experience level bonus
        if 'junior' in job_title_lower or 'entry' in job_desc_lower:
            total_score = min(100, total_score + 5)
        
        # Tool diversity bonus
        tool_diversity = len(set([
            skill for skill in matched_skills 
            if skill in ['sql', 'python', 'r', 'tableau', 'power bi', 'excel']
        ]))
        
        if tool_diversity >= 3:
            total_score = min(100, total_score + 5)
        
        # Step 6: Determine recommendation
        review_threshold = self.thresholds.get('review_threshold', 60)
        
        if total_score >= review_threshold:
            recommendation = 'review'
        elif title_score >= 80:
            # A relevant title without a fetched JD is discovery evidence, not a fit claim.
            recommendation = 'discovered'
        else:
            recommendation = 'skip'
        
        return total_score, matched_skills, recommendation, None


# Test
if __name__ == "__main__":
    matcher = JobMatcher()
    
    test_jobs = [
        ("Junior Data Analyst - SQL, Python, Tableau", "Looking for analyst with SQL, Python, and Tableau skills. Must have experience with data cleaning and statistical analysis."),
        ("Data Analyst - Excel and Power BI", "Need data analyst proficient in Excel pivot tables and Power BI dashboards. R programming is a plus."),
        ("MIS Executive - Reporting", "MIS executive with strong SQL and Excel skills. Experience with statistical analysis and reporting."),
        ("Tableau Developer", "Looking for Tableau developer with Python and SQL background. Must create interactive dashboards."),
        ("Business Analyst - Customer Insights", "Business analyst for customer insights. Experience with segmentation and behavioral analysis."),
    ]
    
    print("\n📊 TESTING ENHANCED MATCHER:\n")
    for title, desc in test_jobs:
        score, skills, rec, reason = matcher.calculate_score(title, desc)
        print(f"Job: {title}")
        print(f"  Score: {score}% | Rec: {rec}")
        print(f"  Skills: {skills}")
        print()