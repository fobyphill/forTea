function ajax_link_def(parent_id, link_code, class_type, span_result){
    if (link_code === '' || parent_id === '')
        span_result.innerText = ''
    else{
        $.ajax({url:'default-link',
            method:'get',
            dataType:'text',
            data: {link_code: link_code, class_type: class_type, parent_id: parent_id},
            success:function(data){
                let url_name = (class_type === 'contract') ? 'contract' : 'manage-object'
                url_name += '?class_id=' + parent_id + '&object_code=' + link_code
                span_result.innerHTML = '<a target="_blank" href="' + url_name + '">' + data + '</a>'
                },
            error: function () {
                span_result.innerText = 'Объект не найден'
            }
        })
    }
}