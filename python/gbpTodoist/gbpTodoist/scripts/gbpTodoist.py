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
prj = importlib.import_module(package_name + '._internal.project')


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

bullet_list = ['-','#','+']

def print_children_recursive(object,level,bullet_level,key='name'):
    if(key=='name'):
        print(level*'   '+object.data[key])
    else:
        print(level*'   '+bullet_list[-bullet_level]+' '+object.data[key])
    if hasattr(object,'tasks'):
        print_tree_recursive(object.tasks,level+1,0,key='content')
    for child in object.children:
        print_children_recursive(child,level+1,bullet_level+1,key=key)

def print_tree_recursive(objects,level=0,bullet_level=0,key='name'):
    for object in objects:
        if not object.parent:
            print_children_recursive(object,level,bullet_level,key=key)

def build_object_tree(objects):
    bad_list = []
    for object in objects:
        object.children = [] 
        object.parent = None
    for object in objects:
        if 'kwargs' in object.data:
            bad_list.append(object)
        else:
            object_id = object.data['id']
            parent_id = object.data['parent_id']
            for candidate in objects:
                candidate_id = candidate.data['id']
                if(candidate_id!=object_id):
                    if(candidate_id==parent_id):
                        object.parent = candidate
                        candidate.children.append(object)
                        break
    return bad_list

def map_tasks_to_projects(projects,tasks):
    for project in projects:
        project.tasks = []
    for task in tasks:
        task_id = task.data['id']
        project_id = task.data['project_id']
        for candidate in projects:
            candidate_id = candidate.data['id']
            if project_id==candidate_id:
                candidate.tasks.append(task)
                break

def build_state_tree(api,projects,tasks):
    # Build project tree
    build_object_tree(projects)

    # Build task tree
    bad_list=build_object_tree(tasks)

    ###########################################
    #if bad_list:
    #    print('Identified the following bad tasks:')
    #    bad_ids_list = []
    #    for bad_item in bad_list:
    #        print('   '+str(bad_item.data))
    #        bad_ids_list.append(bad_item.data['kwargs']['id'])
    #    try:
    #        print('Deleting...',end='')
    #        task_manager = todoist.managers.items.ItemsManager(api)
    #        task_manager.delete(bad_ids_list)
    #        api.commit()
    #    except Exception as e:
    #        print('failed with the following return: '+str(e))
    #        raise
    #    else:
    #        print('Done.')
    ###########################################

    # Map tasks to their projects
    map_tasks_to_projects(projects,tasks)

def find_template_tasks(projects):
    template_list = []
    for project in projects:
        if project.data['name']=='Task Templates':
            parent = project.parent
            if parent:
                for task_parent in parent.tasks:
                    for task_template in project.tasks:
                        if task_template.data['content']==task_parent.data['content']:
                            template_list.append({'content':task_template.data['content'],'project_template':project,'project_target':parent,'task_template':task_template,'task_target':task_parent})

    return template_list

def populate_template_task_recursive(task_manager,subtask_add,task_target):
    print(subtask_add.data['content']+' -> '+task_target.data['content']+' ... ',end='')

    # Check if subtask is already there
    parent_add = None
    for child in task_target.children:
        if subtask_add.data['content']==child.data['content']:
            parent_add = child 
            print("not added (already present).")

    # Create new task
    if not parent_add:
        key_list = ['date_completed', 'all_day','in_history','priority','labels', 'date_lang', 'day_order', 'is_archived','responsible_uid','user_id','checked','date_string','due_date_utc', 'assigned_by_uid','collapsed','is_deleted']
        kwargs_item = {}
        for key in key_list:
            if key in subtask_add.data:
                kwargs_item[key]=subtask_add.data[key]
        #print(task_target.data)
        kwargs_item['item_order']=task_target.data['item_order']
        kwargs_item['indent']=task_target.data['indent']+1
        kwargs_item['parent_id']=task_target.data['id']
        try:
            parent_add = task_manager.add(subtask_add.data['content'],task_target.data['project_id'],**kwargs_item)
        except Exception as e:
            print('failed with the following return: '+str(e))
            raise
        task_target.children.append(parent_add)
        parent_add.parent=task_target
        parent_add.children=[]
        print("added.")

    # Recurse through subtasks
    for child in subtask_add.children:
        populate_template_task_recursive(task_manager,child,parent_add)

def populate_template_tasks(api,template_list):
    try:
        task_manager = todoist.managers.items.ItemsManager(api)
    except Exception as e:
        print('failed with the following return: '+str(e))
        raise
    for item in template_list:
        for subtask_template in item['task_template'].children:
            populate_template_task_recursive(task_manager,subtask_template,item['task_target'])
    try:
        api.commit()
    except Exception as e:
        print('failed with the following return: '+str(e))
        raise

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-k', '--key', 'API_key', help="User's Todoist API Key", type=str, default=None)
def gbpTodoist(API_key):
    """Perform Todoist processing.

    :return: None
    """

    api = todoist.TodoistAPI(API_key)
    api.sync()

    # Build project and task trees
    build_state_tree(api,api.state['projects'],api.state['items'])

    # Print tree
    print("Original tree:")
    print_tree_recursive(api.state['projects'])

    # Find and populate template tasks
    print("Copying tasks:")
    populate_template_tasks(api,find_template_tasks(api.state['projects']))

# Permit script execution
if __name__ == '__main__':
    status = gbpTodoist()
    sys.exit(status)
