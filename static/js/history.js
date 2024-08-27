// Переменные для таймера запуска аякса
var typingTimer;
var doneTypingInterval = 1000;

$('#i_filter_class').keyup(function(){
    clearTimeout(typingTimer);
    if ($('#i_filter_class').val()) {
        typingTimer = setTimeout(prompt_classes, doneTypingInterval);
    }
});

function prompt_classes() {
    let current_class = $('#i_filter_class').val()
    let location = $('#s_location').val()
    let type_class = $('#s_type').val()
    $('#dl_classes').html('')
    $.ajax({url:'get-classes',
            method:'get',
            dataType:'json',
            data: {current_class: current_class, location: location, type_class: type_class},
            success:function(data){
                let dl = $('#dl_classes')
                data.forEach((e) => {
                    let op = document.createElement('option')
                    op.value = e.id
                    op.innerText = e.name + ' ' + e.formula
                    dl.append(op)
                })
            },
            error: function () {}
        })
}

$('#i_name').keyup(function(){
    clearTimeout(typingTimer);
    if ($('#i_name').val()) {
        typingTimer = setTimeout(prompt_name, doneTypingInterval);
    }
});

function prompt_name() {
    let current_name = $('#i_name').val()
    let location = $('#s_location').val()
    let type_class = $('#s_type').val()
    document.getElementById('dl_name').innerHTML = ''
    // $('#dl_name').html('')
    $.ajax({url:'get-name',
            method:'get',
            dataType:'json',
            data: {current_name: current_name, location: location, type_class: type_class},
            success:function(data){
                let dl = $('#dl_name')
                data.forEach((e) => {
                    let op = document.createElement('option')
                    op.value = e.id
                    op.innerText = e.name + ' ' + e.formula
                    dl.append(op)
                })
            },
            error: function () {}
        })
}



function pack_search(){}