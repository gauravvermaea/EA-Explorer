// The pipelines (R6.6-J1, D748): one per eax command and DR tool, from work/jenkins/pipelines.json (eax jenkins
// pipelines writes it from eaxcli/help.txt). Each sends its fields to the agent on the machine, follows the run's
// output and ends with a test report; a run that changes everything carries the installation's name typed in CONFIRM.
import groovy.json.JsonSlurperClassic

def spec = new JsonSlurperClassic().parse(new File('/eax-jenkins/pipelines.json'))
folder('eax') { displayName("EA Explorer: ${spec.installation}, every command") }
// Admin tasks (18 Nov 2026): named pipelines for what is done on the machine, grouped in folders of their own
folder('eax-admin') { displayName("EA Explorer: ${spec.installation}, admin tasks") }
spec.pipelines.findAll { it.folder }.collect { it.folder }.unique().each { f ->
  folder(f) { displayName(spec.pipelines.find { it.folder == f }.group) }
}
// a Groovy map's source for the pipeline's own script: no JSON parser is needed inside Jenkins' sandbox
def groovyMap(Map m) {
  def q = { s -> "'" + s.toString().replace('\\', '\\\\').replace("'", "\\'") + "'" }
  m ? '[' + m.collect { k, v -> q(k) + ': ' + q(v) }.join(', ') + ']' : '[:]'
}

spec.pipelines.each { p ->
  pipelineJob("${p.folder ?: 'eax'}/${p.display ?: p.name}") {
    displayName("${p.display ?: p.name}")
    description("${p.summary}" + (p.confirm ? "\n\nThis changes everything: type the installation's name (${spec.installation}) in CONFIRM." : ""))
    parameters {
      p.params.each { f ->
        def key = f.key.replaceAll('^--', '').replaceAll('/', '_or_').replaceAll('-', '_')
        if (f.type == 'flag') { booleanParam(key, false, f.key) }
        else if (f.type in ['choice', 'flags'] && f.choices) { choiceParam(key, [''] + f.choices, f.placeholder ?: f.key) }
        else { stringParam(key, '', (f.required ? 'Needed: ' : '') + (f.placeholder ?: f.key)) }
      }
      if (p.confirm) { stringParam('CONFIRM', '', "Type the installation's name (${spec.installation}) to go on") }
    }
    definition {
      cps {
        sandbox(true)       // Jenkins' sandbox: no script waits for an administrator's approval (owner, 18 Nov 2026, 12:02)
        script("""
          def KEYS = ${groovyMap(p.params.collectEntries { f -> [(f.key.replaceAll('^--', '').replaceAll('/', '_or_').replaceAll('-', '_')): f.key] } + (p.confirm ? [CONFIRM: 'CONFIRM'] : [:]))}
          pipeline {
            agent any
            options { timestamps(); disableConcurrentBuilds() }
            stages {
              stage('${p.name}') {
                steps {
                  script {
                    def values = [:]
                    KEYS.each { k, original -> if (params[k] != null && params[k] != '' && params[k] != false) { values[original] = params[k] } }
                    def cause = currentBuild.getBuildCauses('hudson.model.Cause\$UserIdCause')
                    def who = cause ? cause[0].userId : 'schedule'
                    writeJSON file: 'request.json', json: [pipeline: '${p.name}', values: values, by: who]
                    def started = sh(returnStdout: true, script: 'curl -sS -X POST -H "X-Eax-Token: \$(cat /run/secrets/EAX_JENKINS_AGENT_TOKEN)" -H "Content-Type: application/json" --data @request.json "\$EAX_AGENT_URL/run"').trim()
                    def run = readJSON text: started
                    if (!run.run) { error("Not started: " + (run.message ?: started)) }
                    echo "Running: " + run.command + " (clicked by " + who + ")"
                    def from = 0
                    def done = null
                    while (done == null) {
                      sleep(time: 3, unit: 'SECONDS')
                      def got = readJSON text: sh(returnStdout: true, script: 'curl -sS -H "X-Eax-Token: \$(cat /run/secrets/EAX_JENKINS_AGENT_TOKEN)" "\$EAX_AGENT_URL/runs/' + run.run + '?from=' + from + '"').trim()
                      if (got.output) { echo got.output.trim() }
                      from = got.next
                      if (got.done) { done = got.exit }
                    }
                    writeFile file: 'report.xml', text: '<testsuite name="eax"><testcase classname="eax" name="${p.name}">' + (done == 0 ? '' : '<failure message="exit ' + done + '"/>') + '</testcase></testsuite>'
                    junit 'report.xml'
                    if (done != 0) { error("eax ended with " + done) }
                  }
                }
              }
            }
          }
        """.stripIndent())
      }
    }
  }
}
