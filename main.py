# encoding: utf-8
import os
import simplejson

import mmpy
import spotimeta


from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

p2p_diff = None
metacache = {}
metadata = spotimeta.Metadata(cache=metacache)

def fetch_top_N_albums(topN):
    mapped = []
    for rank, val, relgrp in p2p_diff.releasegroup:
        try:
            if 'album' in relgrp.description.lower() or 'mixtape' in relgrp.description.lower():
                res = metadata.search_album(relgrp.artist.name+' '+relgrp.name)
                mapped.append((rank, val, res['result'][0]))
        except IndexError:
            print "no album found for "+relgrp.name+" by "+relgrp.artist.name
            continue
        if len(mapped) >= topN:
            break
    return mapped
    
    
def ideal_pair(request):
    """given either a song and an album, or two albums, determine the pair with the minimum timbrel distance, using echonest timbrel features (actually just random seleciton for the moment)"""
    if 'spotify:album' in request.matchdict['first']:
        #doing to way timbrel analysis
        songs_A = []
    else:
        songs_A = []
    #do the same with second album
    #find minimum pair

def topN(request):
    albums = fetch_top_N_albums(int(request.matchdict.get('topN', 10)))
    doc_body = '<br/>'.join([u'no°{rank}: <a href="{uri}">{album} by {artist}</a> with {peers} unique peers today.'.format(rank=rank, uri=album['href'], 
               album=album['name'].encode('utf8'),
               artist=album['artist']['name'], 
               peers=val) for rank, val, album in albums])
    return Response(doc_body)
    
def topNjson(request):
    albums = fetch_top_N_albums(int(request.matchdict.get('topN', 10)))
    return Response(simplejson.dumps({'result':albums}, indent="  "))

if __name__ == '__main__':
    config = Configurator()
    config.add_route('index', '')
    config.add_route('topjson', '/top/{topN}.json')
    config.add_route('top', '/top/{topN}')
    
    config.add_view(topN, route_name='top')
    config.add_view(topN, route_name='index')
    config.add_view(topNjson, route_name='topjson')
    port = int(os.environ.get('PORT', 5000))
    app = config.make_wsgi_app()
    server = make_server('0.0.0.0', port, app)
    print 'made server'
    p2p_diff = mmpy.Chart('p2p daily releasegroups')
    print 'fetched chart'
    server.serve_forever()