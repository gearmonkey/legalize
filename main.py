import mmpy
import spotimeta

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

def fetch_top_N_albums(topN):
    p2p = mmpy.Chart('p2p daily releasegroups')
    mapped = []
    for rank, val, relgrp in p2p.releasegroup:
        try:
            if 'album' in relgrp.description.lower() or 'mixtape' in relgrp.description.lower():
                res = spotimeta.search_album(relgrp.artist.name+' '+relgrp.name)
                mapped.append(res['result'][0])
        except IndexError:
            print "no album found for "+relgrp.name+" by "+relgrp.artist.name
            continue
        if len(mapped) >= topN:
            break
    return mapped
    
    

def topN(request):
    albums = fetch_top_N_albums(int(request.matchdict.get(topN, 10)))
    doc_body = '<br/>'.join([album['name']+' by '+album['artist']['name'] for album in albums])
    return Response(doc_body)
    
if __name__ == '__main__':
    config = Configurator()
    config.add_route('top', '/top/{topN}')
    config.add_view(topN, route_name='top')
    app = config.make_wsgi_app()
    server = make_server('0.0.0.0', 8080, app)
    server.serve_forever()   