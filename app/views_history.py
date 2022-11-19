# coding: utf8
from app import app
from flask import render_template, request, redirect, url_for, flash, abort, Response
from app.models import get_db, get_data_sources
import json
from datetime import datetime

#-------------------------------------------------------
#  TOPIC HISTORY  
#-------------------------------------------------------
@app.route('/dashboard/<int:dash_id>/block/<int:block_id>/history/<int:_from>-<int:_len>')
@app.route('/dashboard/<int:dash_id>/block/<int:block_id>/history/<int:_from>' )
def topic_history( dash_id, block_id, _from=0, _len=None ):

	dashdb = get_db( 'db' )
	dash   = dashdb.get_dash( dash_id )
	block  = dashdb.get_dash_block( block_id )
	topic  = block['topic']
	hist_type = block['hist_type'] 
	hist_size = _len if _len else block['hist_size']
	db_source = get_db( block['source'] )
	values    = db_source.get_values( [topic] )
	tsname    = values[0]['tsname']
	hist_rows = db_source.get_history( tsname=tsname, topic=topic, from_id = None if _from <= 1 else _from, _len=hist_size )
	# print( type(hist_rows[0]["rectime"]) )
	# print( hist_rows[0]["rectime"] )
	if hist_type=='LIST':
		return render_template( 'history/list.html', block=block, dash=dash, rows=hist_rows, _from=_from, _len=hist_size )
	else:
		flash( ('History type %s not supported' % hist_type).decode('utf-8'), 'error' )
		return redirect( url_for('dashboard', id=dash_id) )
		