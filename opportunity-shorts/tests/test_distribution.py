import json
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
import pytest
from shorts.pipeline import Pipeline
from shorts.analytics import collect
from shorts.growth import operations,revenue,discovery
from shorts.growth.store import migrate,now

@pytest.fixture
def p(tmp_path,monkeypatch):
 monkeypatch.setenv('OPP_DB_PATH',str(tmp_path/'db.sqlite'));cfg=tmp_path/'config';cfg.mkdir();(cfg/'shorts.yaml').write_text('llm:\n  provider: template\n')
 obj=Pipeline(cfg);yield obj;obj.close()


def test_upgrade_migration_is_idempotent_and_preserves_delivery(p):
 conn=p.posts.conn;conn.execute("INSERT INTO content_deliveries(content_id,platform,status) VALUES ('a','youtube','uncertain')");conn.commit()
 migrate(conn);migrate(conn)
 assert conn.execute('SELECT status FROM content_deliveries').fetchone()[0]=='uncertain'
 assert conn.execute('SELECT COUNT(*) FROM growth_migrations WHERE version=2').fetchone()[0]==1


def test_analytics_pagination_period_and_missing_metrics(p):
 conn=p.posts.conn;conn.execute("INSERT INTO posts(opportunity_id,script_json,status,youtube_id) VALUES ('a','{}','posted','known')");conn.commit()
 service=Mock()
 def result(**kw):
  if kw['metrics']=='engagedViews':raise ValueError('unsupported')
  return Mock(execute=Mock(return_value={'columnHeaders':[{'name':'video'},{'name':kw['metrics']}],'rows':[['known',12],['unknown',999]]}))
 service.reports().query.side_effect=result
 value=collect(p,service)
 assert value['observations']==7 and 'engaged_views' not in value['retrieved_metrics']
 assert conn.execute('SELECT COUNT(*) FROM metric_observations WHERE object_id=\'unknown\'').fetchone()[0]==0
 from shorts.growth.reporting import report
 data=report(conn);assert not data['videos'] and len(data['period_observations'])==7


def test_revoked_analytics_never_changes_upload_token(p,monkeypatch):
 from shorts import analytics
 monkeypatch.setattr(analytics,'services',Mock(side_effect=ValueError('revoked')))
 result=operations.run_job(p,'analytics',6,lambda:analytics.collect(p))
 assert result['state']=='retry'
 assert p.posts.conn.execute("SELECT status FROM growth_jobs WHERE name='analytics'").fetchone()[0]=='retry'


def test_persistent_job_backoff_recovers(p):
 failing=Mock(side_effect=TimeoutError())
 assert operations.run_job(p,'x',1,failing)['state']=='retry'
 assert operations.run_job(p,'x',1,failing)['state']=='spacing'
 failing.assert_called_once()
 p.posts.conn.execute("UPDATE growth_jobs SET next_at=NULL WHERE name='x'");p.posts.conn.commit()
 assert operations.run_job(p,'x',1,lambda:{'recovered':True})['recovered']


def test_discovery_deduplicates_and_separates_discussion_from_evidence(p):
 cfg={'sources':[{'url':'https://one.example','categories':['applications']},{'url':'https://two.example','categories':['applications']}]}
 a=discovery.add(p.posts.conn,cfg,'discussion','How can I improve my application?','https://discussion.example/q')
 b=discovery.add(p.posts.conn,cfg,'discussion','How can I improve my application?','https://discussion.example/q')
 assert a==b
 row=p.posts.conn.execute('SELECT * FROM career_topics WHERE id=?',(a,)).fetchone()
 assert 'discussion.example' not in row['source_urls']
 assert p.posts.conn.execute('SELECT COUNT(*) FROM discovery_signals').fetchone()[0]==1


def test_insufficient_authoritative_sources_stay_discovery_only(p):
 assert discovery.add(p.posts.conn,{'sources':[]},'trend','How should I verify an internship?','https://example.org') is None
 assert p.posts.conn.execute('SELECT COUNT(*) FROM career_topics').fetchone()[0]==0


def test_revenue_needs_actual_payment_evidence_and_is_idempotent(p):
 conn=p.posts.conn;conn.execute("INSERT INTO outreach_contacts(id,organization,category) VALUES ('c','Company','employer')");conn.commit()
 with pytest.raises(ValueError):revenue.revenue(conn,'c',100,'INR',now(),'')
 a=revenue.revenue(conn,'c',100,'INR',now(),'receipt-1');b=revenue.revenue(conn,'c',100,'INR',now(),'receipt-1')
 assert a==b and revenue.summary(conn)['confirmed_revenue_by_currency']=={'INR':100}
 revenue.activity(conn,'c','contacted','founder-sent-message-reference')
 assert revenue.summary(conn)['sent_outreach_automatically']==0
 assert conn.execute('SELECT follow_up_date FROM outreach_contacts').fetchone()[0]


def test_sync_failure_preserves_retry_and_no_duplicate_write(p,monkeypatch):
 from shorts.growth import sync
 guide={'id':'guide-'+'a'*16,'updated_at':now(),'published_at':now()}
 monkeypatch.setattr(sync,'public_guides',lambda conn:[guide]);monkeypatch.setattr(sync,'settings',lambda:('https://example.org',{}))
 http=Mock();http.put.side_effect=TimeoutError()
 assert sync.sync(p,http)['retrying']==1
 assert sync.sync(p,http)['retrying']==0
 http.put.assert_called_once()
 p.posts.conn.execute('UPDATE guide_sync SET next_at=NULL');p.posts.conn.commit()
 http.put.side_effect=None;http.put.return_value.status_code=201;http.put.return_value.json.return_value={'id':guide['id'],'version':guide['updated_at']}
 assert sync.sync(p,http)['synced']==1
 assert sync.sync(p,http)['synced']==0
 assert http.put.call_count==2


def test_unpublished_drafts_never_sync(p,monkeypatch):
 from shorts.growth import sync
 monkeypatch.setattr(sync,'settings',lambda:('https://example.org',{}));monkeypatch.setattr(sync,'public_guides',lambda conn:[{'id':'draft','published_at':None}])
 http=Mock();sync.sync(p,http);http.put.assert_not_called()

def test_analytics_keeps_paginated_known_video_rows(p):
 from shorts.analytics import collect
 conn=p.posts.conn;conn.execute("INSERT INTO posts(opportunity_id,script_json,status,youtube_id) VALUES ('a','{}','posted','known')");conn.commit()
 service=Mock()
 def query(**kw):
  rows=[['unknown',1]]*199+[['known',12]] if kw['startIndex']==1 else []
  return Mock(execute=Mock(return_value={'columnHeaders':[{'name':'video'},{'name':kw['metrics']}],'rows':rows}))
 service.reports().query.side_effect=query
 result=collect(p,service)
 assert result['observations']==8
 assert any(c.kwargs['startIndex']==201 for c in service.reports().query.call_args_list)
 assert all('filters' in c.kwargs for c in service.reports().query.call_args_list)


def test_experiment_assignment_is_stable_and_has_no_volume_controls(p):
 from shorts.growth.experiments import plan,hook,evaluate
 conn=p.posts.conn;id=plan(conn)
 topic={'title':'Prepare useful examples','question':'How can I improve my application?','category':'applications'}
 first=hook(conn,topic,'guide-test');assert hook(conn,topic,'guide-test')==first
 assert conn.execute('SELECT COUNT(*) FROM experiment_assignments').fetchone()[0]==1
 assert evaluate(conn)['experiments_evaluated']
 data=json.loads(conn.execute('SELECT results FROM growth_experiments WHERE id=?',(id,)).fetchone()[0])
 assert data['bounded_exploration']==[] and data['causal_claim'] is False


def test_job_lease_survives_another_pipeline_instance(p):
 from shorts.growth.store import now
 conn=p.posts.conn
 future=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
 conn.execute('INSERT INTO growth_jobs VALUES (?,?,?,?,?,?)',('leased',future,'working',0,now(),None));conn.commit()
 fn=Mock();assert operations.run_job(p,'leased',1,fn)['state']=='spacing';fn.assert_not_called()
