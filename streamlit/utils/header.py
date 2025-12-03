# utils/header.py
import streamlit as st

def title_page1():
    """Title header for page 1"""
    st.markdown("""
    <style>
        .hero-title {
            text-align: center;
            margin: 2rem 0 3rem 0;
            padding: 2.5rem;
            background: linear-gradient(135deg, #0c4a6e 0%, #0891b2 50%, #22d3ee 100%);
            border-radius: 20px;
            position: relative;
            overflow: hidden;
            box-shadow: 
                0 10px 40px rgba(8, 145, 178, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.2);
        }
        
        .hero-title::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                45deg, 
                transparent 30%, 
                rgba(34, 211, 238, 0.15) 50%, 
                transparent 70%
            );
            animation: shimmer 4s infinite linear;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%) rotate(45deg); }
            100% { transform: translateX(100%) rotate(45deg); }
        }
        
        .hero-content {
            position: relative;
            z-index: 1;
        }
        
        .title-main {
            font-size: 3.5rem;
            font-weight: 900;
            color: white;
            margin-bottom: 0.5rem;
            text-shadow: 
                0 2px 10px rgba(8, 145, 178, 0.3),
                0 4px 20px rgba(6, 182, 212, 0.2);
            letter-spacing: 1px;
            display: inline-block;
        }
        
        .title-text {
            background: linear-gradient(90deg, #ffffff 0%, #e0f2fe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .title-sub {
            font-size: 1.4rem;
            color: rgba(224, 242, 254, 0.9);
            font-weight: 400;
            margin-bottom: 1.5rem;
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
            line-height: 1.6;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        }
    </style>

    <div class="hero-title">
        <div class="hero-content">
            <h1 class="title-main">🛣️ <span class="title-text">Pavement Eye</span></h1>
            <p class="title-sub">Advanced Road Infrastructure Analytics & AI-Powered Monitoring Platform</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def title_page2():
    """Title header for page 2 (analytics)"""
    st.markdown("""
    <style>
        .page-header {
            text-align: center;
            margin: 2rem 0 2.5rem 0;
            padding: 2rem;
        }
        
        .page-title {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(90deg, #1e40af 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .page-subtitle {
            font-size: 1.2rem;
            color: #64748b;
            font-weight: 400;
            max-width: 600px;
            margin: 0 auto;
        }
    </style>

    <div class="page-header">
        <h1 class="page-title">📊 Analytics Dashboard</h1>
        <p class="page-subtitle">Deep insights and trend analysis for road infrastructure</p>
    </div>
    """, unsafe_allow_html=True)

def title_page3():
    """Title header for page 3 (reports)"""
    st.markdown("""
    <style>
        .report-header {
            text-align: center;
            margin: 2rem 0 2.5rem 0;
            padding: 2rem;
        }
        
        .report-title {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(90deg, #059669 0%, #10b981 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .report-subtitle {
            font-size: 1.2rem;
            color: #64748b;
            font-weight: 400;
            max-width: 600px;
            margin: 0 auto;
        }
    </style>

    <div class="report-header">
        <h1 class="report-title">📈 Reports & Insights</h1>
        <p class="report-subtitle">Comprehensive reports and actionable insights</p>
    </div>
    """, unsafe_allow_html=True)

def simple_header(title, subtitle=None, icon="📊"):
    """Generic header for any page"""
    st.markdown(f"""
    <style>
        .simple-header {{
            text-align: center;
            margin: 1.5rem 0 2rem 0;
        }}
        
        .simple-title {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #1e40af;
            margin-bottom: 0.5rem;
        }}
        
        .simple-subtitle {{
            font-size: 1.1rem;
            color: #64748b;
            font-weight: 400;
        }}
    </style>

    <div class="simple-header">
        <h1 class="simple-title">{icon} {title}</h1>
        {f'<p class="simple-subtitle">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)