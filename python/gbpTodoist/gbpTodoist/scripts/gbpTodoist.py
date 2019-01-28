from __future__ import print_function
import os
import sys
import importlib
import click

import todoist

# Infer the name of this package from the path of __file__
package_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
package_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
package_name = os.path.basename(package_root_dir)

# Make sure that what's in this path takes precedence
# over an installed version of the project
sys.path.insert(0, package_parent_dir)

# Import needed internal modules
pkg = importlib.import_module(package_name)
prj = importlib.import_module(package_name + '._internal.project')

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

bullet_list = ['-','#','+']

class task_tree(object):

    def __init__(self,api):
        self.api = api
        self.projects = api.state['projects']
        self.tasks = api.state['items']

        # Build project tree
        self.build_tree(self.projects)

        # Build task tree
        bad_list=self.build_tree(self.tasks)

        ###########################################
        #if bad_list:
        #    pkg.log.open('Identified the following bad tasks:')
        #    bad_ids_list = []
        #    for bad_item in bad_list:
        #        pkg.log.comment('   '+str(bad_item.data))
        #        bad_ids_list.append(bad_item.data['kwargs']['id'])
        #    try:
        #        pkg.log.comment('Deleting...')
        #        task_manager = todoist.managers.items.ItemsManager(api)
        #        task_manager.delete(bad_ids_list)
        #        api.commit()
        #    except Exception as e:
        #        pkg.log.comment('failed with the following return: '+str(e))
        #        raise
        #    else:
        #        pkg.log.comment('Done.')
        #    pkg.log.close(None)
        ###########################################

        # Map tasks to their projects
        for project in self.projects:
            project.tasks = []
        for task in self.tasks:
            task_id = task.data['id']
            project_id = task.data['project_id']
            for candidate in self.projects:
                candidate_id = candidate.data['id']
                if project_id==candidate_id:
                    candidate.tasks.append(task)
                    break

    def _print_children_recursive(self,item,level,bullet_level,key='name'):
        if(key=='name'):
            pkg.log.comment(level*'   '+item.data[key])
        else:
            pkg.log.comment(level*'   '+bullet_list[-bullet_level]+' '+item.data[key])
        if hasattr(item,'tasks'):
            self._print_tree_recursive(item.tasks,level+1,0,key='content')
        for child in item.children:
            self._print_children_recursive(child,level+1,bullet_level+1,key=key)
    
    def _print_tree_recursive(self,items,level=0,bullet_level=0,key='name'):
        for item in items:
            if not item.parent:
                self._print_children_recursive(item,level,bullet_level,key=key)
    
    @staticmethod
    def build_tree(items):
        bad_list = []
        for item in items:
            item.children = [] 
            item.parent = None
        for item in items:
            if 'kwargs' in item.data:
                bad_list.append(item)
            else:
                item_id = item.data['id']
                parent_id = item.data['parent_id']
                for candidate in items:
                    candidate_id = candidate.data['id']
                    if(candidate_id!=item_id):
                        if(candidate_id==parent_id):
                            item.parent = candidate
                            candidate.children.append(item)
                            break
        return bad_list

    def _populate_template_task_recursive(self,task_manager,subtask_add,task_target):
        pkg.log.open(subtask_add.data['content']+' -> '+task_target.data['content']+' ... ')
    
        # Check if subtask is already there
        parent_add = None
        for child in task_target.children:
            if subtask_add.data['content']==child.data['content'] and not (child.data['checked'] or child.data['is_archived']):
                parent_add = child 
                pkg.log.close("not added (already present).")
    
        # Create new task
        if not parent_add:
            key_list = ['date_completed', 'all_day','in_history','priority','labels', 'date_lang', 'day_order', 'is_archived','responsible_uid','user_id','checked','date_string','due_date_utc', 'assigned_by_uid','collapsed','is_deleted']
            kwargs_item = {}
            for key in key_list:
                if key in subtask_add.data:
                    kwargs_item[key]=subtask_add.data[key]
            kwargs_item['item_order']=task_target.data['item_order']
            kwargs_item['indent']=task_target.data['indent']+1
            kwargs_item['parent_id']=task_target.data['id']
            try:
                parent_add = task_manager.add(subtask_add.data['content'],task_target.data['project_id'],**kwargs_item)
            except Exception as e:
                pkg.log.close('failed with the following return: '+str(e))
                raise
            task_target.children.append(parent_add)
            parent_add.parent=task_target
            parent_add.children=[]
            pkg.log.close("added.")
    
        # Recurse through subtasks
        for child in subtask_add.children:
            self._populate_template_task_recursive(task_manager,child,parent_add)
    
    def _find_template_tasks(self):
        template_list = []
        for project in self.projects:
            if project.data['name']=='Task Templates':
                parent = project.parent
                if parent:
                    for task_parent in parent.tasks:
                        for task_template in project.tasks:
                            if task_template.data['content']==task_parent.data['content']:
                                template_list.append({'content':task_template.data['content'],'project_template':project,'project_target':parent,'task_template':task_template,'task_target':task_parent})
    
        return template_list

    def print_tree(self):
        self._print_tree_recursive(self.projects)

    def populate_template_subtasks(self,debug=False):
        pkg.log.open('Populate template subtasks...')
        template_list = self._find_template_tasks()
        if not debug:
            try:
                task_manager = todoist.managers.items.ItemsManager(self.api)
            except Exception as e:
                pkg.log.close('failed with the following return: '+str(e))
                raise
        else:
            task_manager = None
            pkg.log.comment('*** Debug mode is ON ***')
        for item in template_list:
            for subtask_template in item['task_template'].children:
                self._populate_template_task_recursive(task_manager,subtask_template,item['task_target'])
        if not debug:
            try:
                self.api.commit()
            except Exception as e:
                pkg.log.close('failed with the following return: '+str(e))
                raise
        pkg.log.close('Done.')

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-k', '--key', 'API_key', help="User's Todoist API Key", type=str, default=None)
@click.option('-d','--debug/--no-debug', default=False, show_default=True, help='Debug mode? (no writing; dry-run only)')
def gbpTodoist(API_key,debug):
    """Perform Todoist processing.

    :return: None
    """

    # Fetch user's data from server
    api = todoist.TodoistAPI(API_key)
    api.sync()

    # Build trees, etc.
    tree = task_tree(api)

    # Find and populate template tasks
    tree.populate_template_subtasks(debug=debug)
    #tree.print_tree()

# Permit script execution
if __name__ == '__main__':
    status = gbpTodoist()
    sys.exit(status)
