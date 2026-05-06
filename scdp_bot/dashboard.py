import json
import os
import tempfile
from flask import Flask, render_template, abort, send_file
from .db import Session, PCDPAnalysis
from .report_pdf import generate_pdf_report

app = Flask(__name__)
app.jinja_env.filters['fromjson'] = json.loads


@app.route('/')
def index():
    session = Session()
    try:
        analyses = (session.query(PCDPAnalysis)
                    .order_by(PCDPAnalysis.analysis_date.desc())
                    .all())
        stats = {
            'total':    len(analyses),
            'aprovar':  sum(1 for a in analyses if a.status == 'APROVAR'),
            'devolver': sum(1 for a in analyses if a.status == 'DEVOLVER'),
        }
        return render_template('index.html', analyses=analyses, stats=stats)
    finally:
        session.close()


@app.route('/pcdp/<int:aid>')
def detail(aid):
    session = Session()
    try:
        analysis = session.get(PCDPAnalysis, aid)
        if not analysis:
            abort(404)
        report         = json.loads(analysis.report_json)     if analysis.report_json     else {}
        inconsistencias = json.loads(analysis.inconsistencies) if analysis.inconsistencies else []
        financial      = json.loads(analysis.financial_data)  if analysis.financial_data  else {}
        return render_template('detail.html',
                               analysis=analysis,
                               report=report,
                               inconsistencias=inconsistencias,
                               financial=financial)
    finally:
        session.close()


@app.route('/pcdp/<int:aid>/pdf')
def download_pdf(aid):
    session = Session()
    try:
        analysis = session.get(PCDPAnalysis, aid)
        if not analysis:
            abort(404)
        report = json.loads(analysis.report_json) if analysis.report_json else {}
        tmp = tempfile.mkdtemp()
        pdf_path = generate_pdf_report(report, tmp)
        return send_file(pdf_path, as_attachment=True,
                         download_name=os.path.basename(pdf_path))
    finally:
        session.close()


def run(port=5000, debug=False):
    app.run(host='0.0.0.0', port=port, debug=debug)
