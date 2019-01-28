import todoist
api = todoist.TodoistAPI('92f210500cb3c3adaea9e6a2f96815db5c8feeb5')
api.sync()
full_name = api.state['user']['full_name']
print(full_name)

