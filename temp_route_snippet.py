@app.route('/manage_categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if current_user.role != 'hr': # checking base_role usually better but 'hr' works for main admin
        flash('Access denied', 'error'); return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'delete_id' in request.form:
            # Delete Logic
            rid = request.form.get('delete_id')
            role_to_del = Role.query.get(rid)
            if role_to_del:
                db.session.delete(role_to_del)
                db.session.commit()
                flash('Category removed.', 'success')
        else:
            # Add Logic
            name = request.form.get('name')
            prefix = request.form.get('prefix')
            if name and prefix:
                existing = Role.query.filter_by(name=name).first()
                if existing:
                    flash('Category already exists.', 'error')
                else:
                    # Default base_role logic: 
                    # If name contains 'supervisor', base='supervisor', if 'hr', base='hr', else 'employee'
                    base = 'employee'
                    if 'supervisor' in name.lower(): base = 'supervisor'
                    if 'hr' in name.lower() or 'human resource' in name.lower(): base = 'hr'
                    
                    new_role = Role(name=name, prefix=prefix, base_role=base)
                    db.session.add(new_role)
                    db.session.commit()
                    flash(f'Category {name} added.', 'success')
    
    categories = Role.query.all()
    return render_template('categories.html', categories=categories)
