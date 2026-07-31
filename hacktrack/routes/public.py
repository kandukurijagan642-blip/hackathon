from flask import Blueprint, render_template, abort
from models import Certificate

public_bp = Blueprint('public', __name__)

@public_bp.route('/verify-certificate/<token>')
def verify_certificate(token):
    # Lookup the certificate using the verification token
    cert = Certificate.query.filter_by(verification_token=token).first()
    
    if cert:
        status = "Valid"
    else:
        status = "Invalid"
        
    return render_template('public/verify_certificate.html', cert=cert, status=status)
